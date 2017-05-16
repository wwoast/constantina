# Constantina
### A dynamic-content blog platform

## Summary
[Constantina](https://github.com/wwoast/constantina) is a static site generator designed for *grazing*. It is licensed under the [GNU Affero General Public License](https://github.com/wwoast/constantina/blobs/master/LICENSE.md).

## Installing Constantina

### List of Linux dependencies
There are a handful of Linux packages needed (Debian/Ubuntu) to support the ones
installed by Python:

 * `apt-get install libjpeg-dev libffi-dev libssl-dev uwsgi uwsgi-plugin-python`


### List of Python dependencies
You can grab these either from your distro or Python package manager, with the
exception of `python-magic` where Debian's distro version has a totally different
API than the version in `pip`.

Install the Python dependencies manually or from `pip`:

 * `pip install -r requirements.txt`
  * `argon2`, `argon2_cffi`, and `argon2pure` for password hashing
  * `jwcrypto` for managing JWT and JWE session token formats
  * `defusedxml` for occasions where you need to parse HTML files
  * `mutagen` for MP3 length parsing
  * `passlib` as a wrapper for password hashing
  * `pillow` for image operations. Successor to the older `PIL`
  * `python-magic` for file type checks
  * `whoosh` for reverse-index word searching
  * `wsgiref` if you need to use Apache and `mod_cgi`


### Installing Constantina
`python setup.py install -h` describes the options for installing Constantina.
The setup script attempts to install all files necessary for running the 
application, aside from the webserver configuration.

A typical install includes the webserver's username and group that it hosts
files for, the hostname the site will be accessed through, and a port number
that the application will listen on:

```
sudo python ./setup.py install -u www-data -g www-data \
  --hostname codaworry.com --port 9090
```

Although Constantina tries to choose useful defaults when running the install
script, it's a good idea to include at least the values above, so that you
are installing on your system in a consistent way. Since Constantina doesn't
manage webserver configuration, it's important that subsequent installations
use the same port and hostname, to be consistent with an existing Nginx or
Apache configuration.

Once you've installed Constantina, you'll need to choose how the application
will run on your webserver. But first, a couple of relevant details:


### Upgrading Constantina
By default, Constantina installs all required files and configuration for your
site. If you want to install just the Python and HTML updates, you can add the
`--upgrade` switch. This will preserve any card directories you have installed
(i.e. the sample cards won't be added), and won't change any of your config
files in `/etc/constantina/default`.

```
sudo python ./setup.py install --upgrade -u www-data -g www-data
```

Alternatively, you may install just the Python scripts. This puts any HTML or
configuration file placement responsibilties in your hands:

```
python ./setup.py install --scriptonly
```


#### Instances
Constantina uses an idea of *instances*, in case you want to run a staging
copy of the application on the same server as the production copy. This is
a good way to test configuration changes prior to making them on your live
site. Every static resource and configuration for an instance is separated
from the others.

If no instance is specified when running `python ./setup.py install`, the
instance name is called `default`. You'll see that reflected in the paths
to the installed file locations.

Here's an example of installing Constantina twice, under two different
locations and ports, using the *instances* feature:

```
python ./setup.py install -i default --port 9090 \
   --hostname codaworry.com -u www-data -g www-data
python ./setup.py install -i staging --port 9091 \
   --hostname codaworry.com -u www-data -g www-data \
```

#### File Locations
Post-installation, files are installed in the following locations:
 * the data root directory: `/var/www/constantina/default`
  * static HTML (open to the world): `/var/www/constantina/default/public`
  * card data (private, if auth is configured): `/var/www/constantina/default/private`
 * config files: `/etc/constantina/default`
 * Python files: (your system or local Python directories)
 * CGI scripts: `/var/cgi-bin/constantina/default`


### uwsgi+nginx on a private server
The best performing way to install Constantina is with a dedicated
application server such as `gunicorn` or `uwsgi`, with a more general
web server like `nginx` sitting in front and serving static assets out
of its root directory.

`/etc/nginx/sites-available/constantina.conf`:
```
server {
        # Port, config, SSL, and other details here
        listen  8080;
        root  /var/www/constantina/default/public;

        location / {
                uwsgi_pass      localhost:9090;
                include         /etc/nginx/uwsgi_params;

                # uwsgi_param   INSTANCE default;
                uwsgi_param     Host $host;
                uwsgi_param     X-Real-IP $remote_addr;
                uwsgi_param     X-Forwarded-For $proxy_add_x_forwarded_for;
                uwsgi_param     X-Forwarded-Proto $http_x_forwarded_proto;
        }
}
```

`uwsgi.constantina.ini`:
```
[uwsgi]
socket       = localhost:9090
plugin       = python
module       = constantina.constantina
processes    = 3
procname     = constantina-default
chdir        = /var/www/constantina/default/public
max-requests = 5
master

```

At the command line, you can test Constantina by running:
```
uwsgi --ini /etc/constantina/default/uwsgi.ini --daemonize=/path/to/constantina.log
```

### Apache + mod_cgi on Shared Hosting
For those of you still on shared hosting, Constantina will run behind `mod_cgi`
with the included `constantina.cgi` helper script. In the folder where you want
Constantina to treat as your web root folder (i.e. your `public_html` folder),
add a brief Apache config snippet file named `.htaccess`:

```
RewriteEngine on

# All root not directed at files should be processed through CGI
# Replace /cgi-bin/ with your hosting provider's specified scripts folder
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^(.*)$ /cgi-bin/constantina.cgi
SetEnv INSTANCE default
```

Note that this is ''extremely slow performing''. CGI applications must run and reload
all Python resources every time someone visits a site, and on embedded servers, this 
can add many seconds of latency to the initial page load!


### VirtualEnv setup
Shared hosting environments may require you to bundle a bit of code together to support
your Python application.