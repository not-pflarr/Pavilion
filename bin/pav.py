# This is the core pavilion script.
# It shouldn't be run directly; use bin/pav instead.

from logging.handlers import RotatingFileHandler
from pavilion import arguments
from pavilion import commands
from pavilion import config
from pavilion import plugins
import logging
import os
import sys
import traceback

# Pavilion is compatible with python >= 3.4
if sys.version_info[0] != 3 or sys.version_info[1] < 4:
    print("Pavilion requires python 3.4 or higher.", file=sys.stderr)
    sys.exit(-1)

# Get the config, and
try:
    pav_cfg = config.find()
except Exception as err:
    print(err, file=sys.stderr)
    sys.exit(-1)

root_logger = logging.getLogger()

# Set up a directory for tracebacks.
tracebacks_dir = '~/.pavilion/tracebacks'
os.makedirs(tracebacks_dir)

# Put the log file in the lowest common pav config directory we can write to.
for log_dir in reversed(pav_cfg.config_dirs):
    logfile = os.path.join(log_dir, 'pav.log')
    if not os.path.exists(logfile):
        try:
            # 'Touch' the file, in case it doesn't exist. Makes it easier to verify writability
            # in a sec.
            open(logfile, 'a').close()
        except OSError:
            # It's ok if we can't do this.
            pass

    if os.access(logfile, os.W_OK):
        # Set up a rotating logfile than rotates when it gets larger than 1 MB.
        file_handler = RotatingFileHandler(filename=logfile, maxBytes=1024**2, backupCount=3)
        file_handler.format(pav_cfg.log_format)
        file_handler.setLevel(pav_cfg.log_level)
        root_logger.addHandler(file_handler)
        break

# The root logger should pass all messages, even if the handlers filter them.
root_logger.setLevel(logging.DEBUG)

# Initialize all the plugins
try:
    plugins.initialize_plugins(pav_cfg)
except plugins.PluginError as err:
    print("Error initializing plugins: {}".format(err), file=sys.stderr)
    sys.exit(-1)

# Get and parse the arguments
parser = arguments.get_parser()
try:
    args = parser.parse_args()
except Exception:
    # TODO: Handle argument parsing errors correctly.
    raise

# Add a stream to stderr if we're in verbose mode, or if no other handler is defined.
if args.verbose or not root_logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.level(logging.DEBUG)
    handler.format(pav_cfg.log_format)
    root_logger.addHandler(handler)

# Create the basic directories in the working directory
for path in [pav_cfg.working_dir,
             os.path.join(pav_cfg.working_dir, 'builds'),
             os.path.join(pav_cfg.working_dir, 'tests'),
             os.path.join(pav_cfg.working_dir, 'downloads')]:
    if not os.path.exists(path):
        try:
            os.mkdir(path)
        except OSError as err:
            # Handle potential race conditions with directory creation.
            if os.path.exists(path):
                # Something else created the directory
                pass
            else:
                print("Could not create base directory '{}': {}".format(path, err))
                sys.exit(1)

try:
    cmd = commands.get_command(args.command_name)
except KeyError:
    print("Unknown command {}.".format(args.command_name), file=sys.stderr)
    sys.exit(-1)

try:
    sys.exit(cmd.run(pav_cfg, args))
except Exception as err:
    print("Unknown error running command {}: {}.".format(args.command_name, err))
    traceback_file = os.path.join(tracebacks_dir, str(os.getpid()))
    with open(traceback_file, 'w') as tb:
        tb.write(traceback.format_exc())
    print("Traceback saved in {}".format(traceback_file))
    sys.exit(-1)
