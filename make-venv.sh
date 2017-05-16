#!/bin/sh

# Change this to whatever your domain is
CONSTANTINA_HOSTNAME=example.com

# For virtualenvs, recommend keeping the instance name and path fixed.
# Otherwise you need to edit shared.py and add new locations that
# the constantina.ini file will be found in.
CONSTANTINA_INSTANCE=default
VENV_PATH=$HOME/constantina

virtualenv $VENV_PATH &&
. $VENV_PATH/bin/activate &&
pip install -r requirements.txt


# HACK so that constantina_configure finds the config path to make edits
ln -s $VENV_PATH/etc .

# All pathnames below are relative to the $VENV_PATH
python setup.py install \
   --instance $CONSTANTINA_INSTANCE \
   --hostname $CONSTANTINA_HOSTNAME \
   --config-root etc/constantina/$CONSTANTINA_INSTANCE \
   --cgi-bin cgi-bin \
   --data-root html

# HACK remove the etc symlink
rm etc

deactivate
tar czf $VENV_PATH/../constantina-venv.tar.gz $VENV_PATH
