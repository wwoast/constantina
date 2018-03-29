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

virtualenv -p $PY_VER $VENV_PATH &&
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

cd $VENV_PATH/.. && tar czf constantina-venv.tar.gz `basename $VENV_PATH`
