# (c) 2015-2017 Acellera Ltd http://www.acellera.com
# All Rights Reserved
# Distributed under HTMD Software License Agreement
# No redistribution in whole or part
#
import warnings
import numpy as np
import random
from htmd.util import _getNcpus
from htmd.projections.metric import Metric, _projectionGenerator
from htmd.progress.progress import ProgressBar
from htmd.units import convert as unitconvert
from joblib import Parallel, delayed
import logging
logger = logging.getLogger(__name__)


class TICA(object):
    """ Class for calculating the TICA projections of a MetricData  object

    Time-based Independent Component Analysis
    Projects your data on the slowest coordinates identified for a
    given lagtime.

    Parameters
    ----------
    data : :class:`MetricData <htmd.metricdata.MetricData>` object
        The object whose data we wish to project onto the top TICA dimensions
    lag : int
        The correlation lagtime to use for TICA
    units : str
        The units of lag. Can be 'frames' or any time unit given as a string.
    dimensions : list
        A list of dimensions of the original data on which to apply TICA. All other dimensions will stay unaltered.
        If None is given, it will apply on all dimensions.

    Example
    -------
    >>> from htmd.projections.tica import TICA
    >>> tica = TICA(data,20)

    References
    ----------
    Perez-Hernandez, G. and Paul, F. and Giorgino, T. and de Fabritiis, G.
    and Noe, F. (2013) Identification of slow molecular order parameters
    for Markov model construction. J. Chem. Phys., 139 . 015102.
    """

    def __init__(self, data, lag, units='frames', dimensions=None):
        from pyemma.coordinates.transform.tica import TICA as TICApyemma

        self.data = data
        self.dimensions = dimensions

        if isinstance(data, Metric):  # Memory efficient TICA projecting trajectories on the fly
            if units != 'frames':
                raise RuntimeError('Cannot use delayed projection TICA with units other than frames for now. Report this to HTMD issues.')
            self.tic = TICApyemma(lag)
            metr = data

            p = ProgressBar(len(metr.simulations))
            for proj in _projectionGenerator(metr, _getNcpus()):
                for pro in proj:
                    if pro is None:
                        continue
                    if self.dimensions is None:
                        self.tic.partial_fit(pro[0])
                    else:  # Sub-select dimensions for fitting
                        self.tic.partial_fit(pro[0][:, self.dimensions])
                p.progress(len(proj))
            p.stop()
        else:  # In-memory TICA
            lag = unitconvert(units, 'frames', lag, data.fstep)
            if lag == 0:
                raise RuntimeError('Lag time conversion resulted in 0 frames. Please use a larger lag-time for TICA.')

            self.tic = TICApyemma(lag)
            if self.dimensions is None:
                datalist = data.dat.tolist()
            else:  # Sub-select dimensions for fitting
                datalist = [x[:, self.dimensions].copy() for x in data.dat]
            self.tic.fit(datalist)

    def project(self, ndim=None):
        """ Projects the data object given to the constructor onto the top `ndim` TICA dimensions

        Parameters
        ----------
        ndim : int
            The number of TICA dimensions we want to project the data on. If None is given it will use choose a number
            of dimensions to cover 95% of the kinetic variance.

        Returns
        -------
        dataTica : :class:`MetricData <htmd.metricdata.MetricData>` object
            A new :class:`MetricData <htmd.metricdata.MetricData>` object containing the TICA projected data

        Example
        -------
        >>> from htmd.projections.tica import TICA
        >>> tica = TICA(data,20)
        >>> dataTica = tica.project(5)
        """
        if ndim is not None:
            self.tic.set_params(dim=ndim)

        keepdata = []
        keepdim = None
        keepdimdesc = None
        if isinstance(self.data, Metric):  # Memory efficient TICA projecting trajectories on the fly
            proj = []
            refs = []
            fstep = None

            metr = self.data
            p = ProgressBar(len(metr.simulations))
            k = -1
            droppedsims = []
            for projecteddata in _projectionGenerator(metr, _getNcpus()):
                for pro in projecteddata:
                    k += 1
                    if pro is None:
                        droppedsims.append(k)
                        continue
                    if self.dimensions is not None:
                        numDimensions = pro[0].shape[1]
                        keepdim = np.setdiff1d(range(numDimensions), self.dimensions)
                        keepdata.append(pro[0][:, keepdim])
                        proj.append(self.tic.transform(pro[0][:, self.dimensions]).astype(np.float32))  # Sub-select dimensions for projecting
                    else:
                        proj.append(self.tic.transform(pro[0]).astype(np.float32))
                    refs.append(pro[1])
                    if fstep is None:
                        fstep = pro[2]
                p.progress(len(projecteddata))
            p.stop()

            simlist = self.data.simulations
            simlist = np.delete(simlist, droppedsims)
            ref = np.array(refs, dtype=object)
            parent = None
            if self.dimensions is not None:
                from htmd.projections.metric import _singleMolfile
                from htmd.molecule.molecule import Molecule
                (single, molfile) = _singleMolfile(metr.simulations)
                if single:
                    keepdimdesc = metr.getMapping(Molecule(molfile))
                    keepdimdesc = keepdimdesc.ix[keepdim]
        else:
            if ndim is not None and self.data.numDimensions < ndim:
                raise RuntimeError('TICA cannot increase the dimensionality of your data. Your data has {} dimensions and you requested {} TICA dimensions'.format(self.data.numDimensions, ndim))

            if self.dimensions is not None:
                keepdim = np.setdiff1d(range(self.data.numDimensions), self.dimensions)
                keepdata = [x[:, keepdim] for x in self.data.dat]
                if self.data.map is not None:
                    keepdimdesc = self.data.map.ix[keepdim]
            proj = self.tic.get_output()
            simlist = self.data.simlist
            ref = self.data.ref
            fstep = self.data.fstep
            parent = self.data

        # If TICA is done on a subset of dimensions, combine non-projected data with projected data
        if self.dimensions is not None:
            newproj = []
            for k, t in zip(keepdata, proj):
                newproj.append(np.hstack((k, t)))
            proj = newproj

        if ndim is None:
            logger.info('Kept {} dimension(s) to cover 95% of kinetic variance.'.format(self.tic.dimension()))

        from htmd.metricdata import MetricData
        datatica = MetricData(dat=np.array(proj), simlist=simlist, ref=ref, fstep=fstep, parent=parent)
        from pandas import DataFrame
        # TODO: Make this messy pandas creation cleaner. I'm sure I can append rows to DataFrame
        types = []
        indexes = []
        description = []
        for i in range(ndim):
            types += ['tica']
            indexes += [-1]
            description += ['TICA dimension {}'.format(i+1)]
        datatica.map = DataFrame({'type': types, 'atomIndexes': indexes, 'description': description})

        if self.dimensions is not None and keepdimdesc is not None:  # If TICA is done on a subset of dims
            datatica.map = keepdimdesc.append(datatica.map, ignore_index=True)

        return datatica


if __name__ == '__main__':
    from htmd import *
    from htmd.home import home
    from os.path import join

    testfolder = home(dataDir='villin')

    sims = simlist(glob(join(testfolder, '*', '')), join(testfolder, 'filtered.pdb'))
    met = Metric(sims[0:2])
    met.projection(MetricSelfDistance('protein and name CA'))
    data = met.project()
    data.fstep = 0.1

    tica = TICA(data, 2, dimensions=range(2, 10))
    datatica = tica.project(2)
    tica5 = TICA(data, 0.2, units='ns', dimensions=range(2, 10))
    datatica5 = tica5.project(2)
    expected = [[ 3.69098878, -0.33862674,  0.85779184],
                [ 3.77816105, -0.31887317,  0.87724227],
                [ 3.83537507, -0.11878026,  0.65236956]]
    assert np.allclose(np.abs(datatica.dat[0][-3:, -3:]), np.abs(np.array(expected, dtype=np.float32)), rtol=0, atol=0.01)
    assert np.allclose(np.abs(datatica5.dat[0][-3:, -3:]), np.abs(np.array(expected, dtype=np.float32)), rtol=0, atol=0.01)
    assert np.all(datatica.map.ix[[587, 588]].type == 'tica')
    assert np.all(datatica.map.ix[range(587)].type == 'distance')
    print('In-memory TICA with subset of dimensions passed test.')

    tica2 = TICA(met, 2, dimensions=range(2, 10))
    datatica2 = tica2.project(2)
    assert np.allclose(np.abs(datatica2.dat[0][-3:, -3:]), np.abs(np.array(expected, dtype=np.float32)), rtol=0, atol=0.01)
    assert np.all(datatica2.map.ix[[587, 588]].type == 'tica')
    assert np.all(datatica2.map.ix[range(587)].type == 'distance')
    print('Streaming TICA with subset of dimensions passed test.')

    #assert np.max(np.abs(datatica.dat[0][:, -2:]) - np.abs(datatica2.dat[0][:, -2:])) < 0.01, 'Streaming and memory subdim TICA inconsistent.'

    tica3 = TICA(data, 2)
    datatica3 = tica3.project(2)
    expected = [[-1.36328638, -0.35354128],
                [-1.35348749, -0.13028328],
                [-1.43249917, -0.31004715]]
    assert np.allclose(np.abs(datatica3.dat[0][-3:, :]), np.abs(np.array(expected, dtype=np.float32)), rtol=0, atol=0.01)
    assert np.all(datatica3.map.ix[[0, 1]].type == 'tica')
    print('In-memory TICA passed test.')

    tica4 = TICA(met, 2)
    datatica4 = tica4.project(2)
    assert np.allclose(np.abs(datatica4.dat[0][-3:, :]), np.abs(np.array(expected, dtype=np.float32)), rtol=0, atol=0.01)
    assert np.all(datatica4.map.ix[[0, 1]].type == 'tica')
    print('Streaming TICA passed test.')

    assert np.max(np.abs(datatica4.dat[0]) - np.abs(datatica3.dat[0])) < 0.01, 'Streaming and memory TICA inconsistent.'
