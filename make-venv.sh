#!/bin/sh

# --------------------------------------------------------------------------- #
# Change this to whatever your domain is
CONSTANTINA_HOSTNAME=example.com

# For virtualenvs, recommend keeping the instance name and path fixed.
# Otherwise you need to edit shared.py and add new locations that
# the constantina.ini file will be found in.
CONSTANTINA_INSTANCE=default
VENV_PATH=$HOME/constantina
CONFIG_ROOT=etc/constantina/$CONSTANTINA_INSTANCE
CGI_BIN=cgi-bin
DATA_ROOT=html

PY_VER="python3.5"

# --------------------------------------------------------------------------- #

virtualenv -p $PY_VER --no-site-packages --always-copy --clear $VENV_PATH &&
. $VENV_PATH/bin/activate &&
pip3 install -r requirements.txt

# HACK so that constantina_configure finds the config path to make edits
ln -s $VENV_PATH/etc .

# All pathnames below are relative to the $VENV_PATH
python3 setup.py install \
   --instance $CONSTANTINA_INSTANCE \
   --hostname $CONSTANTINA_HOSTNAME \
   --config-root $CONFIG_ROOT \
   --cgi-bin $CGI_BIN \
   --data-root $DATA_ROOT

# HACK remove the etc symlink
rm etc

deactivate

# HACK copy necessary default libraries
cp -r /usr/lib/$PY_VER/ctypes $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/email $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/http $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/json $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/logging $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/urllib $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/wsgiref $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/xml $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/_compat_pickle.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/ast.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/calendar.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/contextlib.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/configparser.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/datetime.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/dis.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/decimal.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/dummy_threading.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/enum.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/glob.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/inspect.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/ipaddress.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/numbers.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/opcode.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/platform.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/pickle.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/queue.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/quopri.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/signal.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/selectors.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/socket.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/string.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/stringprep.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/subprocess.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/textwrap.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/threading.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/traceback.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/uu.py $VENV_PATH/lib/$PY_VER
cp -r /usr/lib/$PY_VER/uuid.py $VENV_PATH/lib/$PY_VER

cd $VENV_PATH/.. && tar czf constantina-venv.tar.gz `basename $VENV_PATH`
