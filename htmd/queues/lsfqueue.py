# (c) 2015-2017 Acellera Ltd http://www.acellera.com
# All Rights Reserved
# Distributed under HTMD Software License Agreement
# No redistribution in whole or part
#
import os
import shutil
import random
import string
import numpy as np
from subprocess import check_output, CalledProcessError
from htmd.protocols.protocolinterface import ProtocolInterface, TYPE_FLOAT, TYPE_INT, RANGE_ANY, RANGE_0POS, RANGE_POS
from htmd.queues.simqueue import SimQueue
import logging
logger = logging.getLogger(__name__)


class LsfQueue(SimQueue, ProtocolInterface):
    """ Queue system for LSF

    Parameters
    ----------
    jobname : str, default=None
        Job name (identifier)
    queue : str, default=None
        The queue to run on
    ngpu : int, default=1
        Number of GPUs to use for a single job
    memory : int, default=4000
        Amount of memory per job (MB)
    walltime : int, default=None
        Job timeout (hour:min or min)
    environment : list of strings, default=None
        Things to run before the job (sourcing envs).
    resources : str, default=None
        Resources of the queue
    outputstream : str, default='slurm.%N.%j.out'
        Output stream.
    errorstream : str, default='slurm.%N.%j.err'
        Error stream.

    Examples
    --------
    >>> from htmd import *
    >>> s = LsfQueue()
    >>> s.jobname = 'simulation1'
    >>> s.queue = 'multiscale'
    >>> s.submit('/my/runnable/folder/')  # Folder containing a run.sh bash script
    """
    def __init__(self):
        super().__init__()
        self._cmdString('jobname', 'str', 'Job name (identifier)', None)
        self._cmdString('queue', 'str', 'The queue to run on', None)
        self._cmdValue('ngpu', 'int', 'Number of GPUs to use for a single job', 1, TYPE_INT, RANGE_0POS)
        self._cmdValue('memory', 'int', 'Amount of memory per job (MB)', 4000, TYPE_INT, RANGE_0POS)
        self._cmdValue('walltime', 'int', 'Job timeout (hour:min or min)', None, TYPE_INT, RANGE_POS)
        self._cmdString('resources', 'str', 'Resources of the queue', None)
        self._cmdList('environment', 'list', 'Things to run before the job (sourcing envs).', None)
        self._cmdString('outputstream', 'str', 'Output stream.', 'lsf.%J.out')
        self._cmdString('errorstream', 'str', 'Error stream.', 'lsf.%J.err')
        self._cmdString('datadir', 'str', 'The path in which to store completed trajectories.', None)
        self._cmdString('trajext', 'str', 'Extension of trajectory files. This is needed to copy them to datadir.', 'xtc')

        # Find executables
        self._qsubmit = LsfQueue._find_binary('bsub')
        self._qinfo = LsfQueue._find_binary('bqueues')
        self._qcancel = LsfQueue._find_binary('bkill')
        self._qstatus = LsfQueue._find_binary('bjobs')

        self._sentinel = 'htmd.queues.done'
        # For synchronous
        self._dirs = []

        # Specific automatic guessing
        ret = check_output(self._qinfo)
        if 'phase6_normal' in ret.decode('ascii'):
            if self.environment is None:
                self.environment = ['source /home/model/MD-SOFTWARE/model_md.bashrc', 'source /home/model/miniconda3/htmd.bashrc']
                logger.info('environment set to {}'.format(self.environment))
            if self.resources is None:
                self.resources = '"{}"'.format('rusage[ngpus_excl_p=1],span[hosts=1]')
                logger.info('resources set to {}'.format(self.resources))
        if 'gpu_priority' in ret.decode('ascii'):
            if self.environment is None:
                self.environment = ['module load acemd', 'module load acellera/test', 'module load gaussian']
                logger.info('environment set to {}'.format(self.environment))
            if self.resources is None:
                self.resources = '"{}"'.format('select[ngpus>0] rusage[ngpus_excl_p=1]')
                logger.info('resources set to {}'.format(self.resources))

    @staticmethod
    def _find_binary(binary):
        ret = shutil.which(binary, mode=os.X_OK)
        if not ret:
            raise FileNotFoundError("Could not find required executable [{}]".format(binary))
        ret = os.path.abspath(ret)
        return ret

    def _createJobScript(self, fname, workdir, runsh):
        workdir = os.path.abspath(workdir)
        with open(fname, 'w') as f:
            f.write('#!/bin/bash\n')
            f.write('#\n')
            f.write('#BSUB -J {}\n'.format(self.jobname))
            f.write('#BSUB -q {}\n'.format(self.queue))
            f.write('#BSUB -n {}\n'.format(self.ngpu))
            f.write('#BSUB -M {}\n'.format(self.memory))
            f.write('#BSUB {}\n'.format(workdir))
            f.write('#BSUB -o {}\n'.format(self.outputstream))
            f.write('#BSUB -e {}\n'.format(self.errorstream))
            if self.walltime is not None:
                f.write('#BSUB -W {}\n'.format(self.walltime))
            if self.resources is not None:
                f.write('#BSUB -R {}\n'.format(self.resources))
            # Trap kill signals to create sentinel file
            f.write('\ntrap "touch {}" EXIT SIGTERM\n'.format(os.path.normpath(os.path.join(workdir, self._sentinel))))
            f.write('\n')
            if self.environment is not None:
                for call in self.environment:
                    f.write('{}\n'.format(call))
            f.write('\ncd {}\n'.format(workdir))
            f.write('{}'.format(runsh))

            # Move completed trajectories
            if self.datadir is not None:
                datadir = os.path.abspath(self.datadir)
                if not os.path.isdir(datadir):
                    os.mkdir(datadir)
                simname = os.path.basename(os.path.normpath(workdir))
                # create directory for new file
                odir = os.path.join(datadir, simname)
                os.mkdir(odir)
                f.write('\nmv *.{} {}'.format(self.trajext, odir))

        os.chmod(fname, 0o700)

    def retrieve(self):
        # Nothing to do
        pass

    def _autoQueueName(self):
        ret = check_output(self._qinfo)
        return ','.join(np.unique([i.split()[0].strip('*') for i in ret.decode('ascii').split('\n')[1:-1]]))

    def _autoJobName(self, path):
        return os.path.basename(os.path.abspath(path)) + '_' + ''.join([random.choice(string.digits) for _ in range(5)])

    def submit(self, dirs):
        """ Submits all directories

        Parameters
        ----------
        dirs : list
            A list of executable directories.
        """
        if isinstance(dirs, str):
            dirs = [dirs, ]
        self._dirs.extend(dirs)

        if self.queue is None:
            self.queue = self._autoQueueName()

        # if all folders exist, submit
        for d in dirs:
            logger.info('Queueing ' + d)

            if self.jobname is None:
                self.jobname = self._autoJobName(d)

            runscript = os.path.abspath(os.path.join(d, 'run.sh'))

            # Clean sentinel files , if existent
            if os.path.exists(os.path.join(d, self._sentinel)):
                try:
                    os.remove(os.path.join(d, self._sentinel))
                except:
                    logger.warning('Could not remove {} sentinel from {}'.format(self._sentinel, d))
                else:
                    logger.info('Removed existing {} sentinel from {}'.format(self._sentinel, d))

            if not os.path.exists(runscript):
                raise FileExistsError('File {} does not exist.'.format(runscript))
            if not os.access(runscript, os.X_OK):
                raise PermissionError('File {} does not have execution permissions.'.format(runscript))

            jobscript = os.path.abspath(os.path.join(d, 'job.sh'))
            self._createJobScript(jobscript, d, runscript)
            try:
                ret = check_output(self._qsubmit + " < " + jobscript, shell=True)
                logger.debug(ret)
            except:
                raise

    def inprogress(self):
        """ Returns the sum of the number of running and queued workunits of the specific group in the engine.

        Returns
        -------
        total : int
            Total running and queued workunits
        """
        import time
        import getpass
        if self.queue is None:
            self.queue = self._autoQueueName()
        if self.jobname is None:
            raise ValueError('The jobname needs to be defined.')
        user = getpass.getuser()
        cmd = [self._qstatus, '-J', self.jobname, '-u', user, '-q', self.queue]
        logger.debug(cmd)

        # This command randomly fails so I need to allow it to repeat or it crashes adaptive
        tries = 0
        while tries < 3:
            try:
                ret = check_output(cmd)
            except CalledProcessError:
                if tries == 2:
                    raise
                tries += 1
                time.sleep(3)
                continue
            break

        logger.debug(ret.decode("ascii"))

        # TODO: check lines and handle errors
        l = ret.decode("ascii").split("\n")
        l = len(l) - 2
        if l < 0:
            l = 0  # something odd happened
        return l

    def notcompleted(self):
        """Returns the sum of the number of job directories which do not have the sentinel file for completion.

        Returns
        -------
        total : int
            Total number of directories which have not completed
        """
        total = 0
        if len(self._dirs) == 0:
            raise RuntimeError('This method relies on running synchronously.')
        for i in self._dirs:
            if not os.path.exists(os.path.join(i, self._sentinel)):
                total += 1
        return total

    def stop(self):
        """ Cancels all currently running and queued jobs
        """
        import getpass
        if self.queue is None:
            self.queue = self._autoQueueName()
        user = getpass.getuser()
        cmd = [self._qcancel, '-J', self.jobname, '-u', user, '-q', self.queue]
        logger.debug(cmd)
        ret = check_output(cmd)
        logger.debug(ret.decode("ascii"))

    def wait(self, sentinel=False):
        """ Blocks script execution until all queued work completes

        Parameters
        ----------
        sentinel : bool, default=False
            If False, it relies on the queueing system reporting to determine the number of running jobs. If True, it
            relies on the filesystem, in particular on the existence of a sentinel file for job completion.

        Examples
        --------
        >>> LsfQueue.wait()
        """
        from time import sleep
        import sys

        while (self.inprogress() if not sentinel else self.notcompleted()) != 0:
            sys.stdout.flush()
            sleep(5)

if __name__ == "__main__":
    """
    s=Slurm( name="testy", partition="gpu")
    s.submit("test/dhfr1" )
    ret= s.inprogress( debug=False)
    print(ret)
    print(s)
    pass
    """
