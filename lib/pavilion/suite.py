from pavilion.test_config import PavTest
from pavilion.lockfile import TimeoutError
from pavilion import utils

import logging
import os


class SuiteError(RuntimeError):
    """An error in managing a suite of tests."""
    pass


class Suite:
    """Suites are a collection of tests. Every time """

    SUITE_ID_DIGITS = 7
    LOGGER_FMT = 'suite({})'

    def __init__(self, pav_cfg, tests, _id=None):
        """Initialize the suite.
        :param pav_cfg: The pavilion configuration object.
        :param list tests: The list of test objects that belong to this suite.
        :param int _id: The test id number. If this is given, it implies that
            we're regenerating this suite from saved files.
        """

        self.pav_cfg = pav_cfg
        self.tests = {test.id: test for test in tests}

        if not tests:
            raise SuiteError("You cannot create a suite of zero tests.")

        suites_path = os.path.join(self.pav_cfg.working_dir, 'suites')

        # We're creating this suite from scratch.
        if _id is None:
            # Get the suite id and path.
            try:
                self.id, self.path = utils.create_id_dir(suites_path)
            except (OSError, TimeoutError) as err:
                raise SuiteError(
                    "Could not get id or suite directory in '{}': {}"
                    .format(suites_path, err))

            # Create a soft link to the test directory of each test in the
            # suite.
            for test in tests:
                link_path = utils.make_id_path(self.path, test.id)

                try:
                    os.symlink(test.path, link_path)
                except OSError as err:
                    raise SuiteError(
                        "Could not link test '{}' in suite at '{}': {}"
                        .format(test.path, link_path, err))

            # Save the last suite we created to the .pavilion directory
            # in the user's home dir. Pavilion commands can use this so the
            # user doesn't actually have to know the suite_id of tests.
            try:
                user_pav_dir = os.path.expanduser('~/.pavilion')
                if not os.path.exists(user_pav_dir):
                    os.mkdir(user_pav_dir)

                last_suite_fn = os.path.join(user_pav_dir, 'last_suite')
                with open(last_suite_fn, 'w') as last_suite_file:
                    last_suite_file.write(str(self.id))
            except (IOError, OSError):
                # It's ok if we can't write this file.
                pass
        else:
            self.id = _id
            self.path = utils.make_id_path(suites_path, self.id)

        self._logger = logging.getLogger(self.LOGGER_FMT.format(self.id))

    @classmethod
    def from_id(cls, pav_cfg, id_):

        suites_path = os.path.join(pav_cfg.working_dir, 'suites')
        suite_path = utils.make_id_path(suites_path, id_)

        if not os.path.exists(suite_path):
            raise SuiteError("No such suite found: '{}' at '{}'"
                             .format(id_, suite_path))

        logger = logging.getLogger(cls.LOGGER_FMT.format(id_))

        tests = []
        for path in os.listdir(suite_path):
            link_path = os.path.join(suite_path, path)
            if os.path.islink(link_path) and os.path.isdir(link_path):
                try:
                    test_id = int(os.path.basename(link_path))
                except ValueError:
                    logger.info(
                        "Bad test id in suite from dir '{}'".format(link_path)
                    )
                    continue

                tests.append(PavTest.from_id(pav_cfg, test_id=test_id))
            else:
                logger.info(
                    "Polluted suite directory in suite '{}'".format(suite_path)
                )
                raise ValueError(link_path)

        return cls(pav_cfg, tests, _id=id_)

    @property
    def ts(self):
        """Return the unix timestamp for this suite, based on the last
        modified date for the test directory."""
        # Leave it up to the caller to deal with time properly.
        return os.stat(self.path).st_mtime
