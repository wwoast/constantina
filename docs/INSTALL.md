# Constantina
### A dynamic-content blog platform

## Summary
[Constantina](https://github.com/wwoast/constantina) is a static site generator designed for *grazing*. It is licensed under the [GNU Affero General Public License](https://github.com/wwoast/constantina/blobs/master/LICENSE.md).

## Installing Constantina

### List of Linux dependencies
There are a handful of Linux packages needed (Debian/Ubuntu) to support the ones
installed by Python:

 * `apt-get install libjpeg-dev python3-pip uwsgi uwsgi-plugin-python3`


### List of Python dependencies
You can grab these either from your distro or Python package manager, with the
exception of `python-magic` where Debian's distro version has a totally different
API than the version in `pip`.

Install the Python dependencies manually or from `pip`:

 * `pip3 install -r requirements.txt`
   * `defusedxml` for occasions where you need to parse HTML files
   * `mutagen` for MP3 length parsing
   * `passlib` as a wrapper for password hashing
   * `pillow` for image operations. Successor to the older `PIL`
   * `python-magic` for file type checks
   * `whoosh` for reverse-index word searching
   * `wsgiref` if you need to use Apache and `mod_cgi`
 * Second-order dependencies for the above libraries include:
   * `appdirs`, `pyparsing`, `idna`


### Running the Installer
`python3 setup.py install -h` describes the options for installing Constantina.
The setup script attempts to install all files necessary for running the 
application, aside from the webserver configuration.

A typical install includes the webserver's username and group that it hosts
files for, the hostname the site will be accessed through, and a port number
that the application will listen on:

```
sudo python3 ./setup.py install -u www-data -g www-data \
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
sudo python3 ./setup.py install --upgrade -u www-data -g www-data
```

Alternatively, you may install just the Python scripts. This puts any HTML or
configuration file placement responsibilties in your hands:

```
python3 ./setup.py install --scriptonly
```


### Instances
Constantina uses an idea of *instances*, in case you want to run a staging
copy of the application on the same server as the production copy. This is
a good way to test configuration changes prior to making them on your live
site. Every static resource and configuration for an instance is separated
from the others.

If no instance is specified when running `python3 ./setup.py install`, the
instance name is called `default`. You'll see that reflected in the paths
to the installed file locations.

Here's an example of installing Constantina twice, under two different
locations and ports, using the *instances* feature:

```
python3 ./setup.py install -i default --port 9090 \
   --hostname codaworry.com -u www-data -g www-data
python3 ./setup.py install -i staging --port 9091 \
   --hostname codaworry.com -u www-data -g www-data \
```

Instances are specified as an environment variable `INSTANCE`, provided in
the web server configuration. This allows you to manage which external port
on a web server virtualhost maps to a specific instance of Constantina.
The `INSTANCE` value fills out the `/etc/constantina/$INSTANCE/` path that
holds this copy of Constantina's configuration settings.


### File Locations
Post-installation, files are installed in the following locations:
 * the data root directory: `/var/www/constantina/default`
   * static HTML (open to the world): `/var/www/constantina/default/public`
   * card data (private, if auth is configured): `/var/www/constantina/default/private`
 * config files: `/etc/constantina/default`
 * Python files: (your system or local Python directories)
 * CGI scripts: `/var/cgi-bin/constantina/default`


## Configuring the Web Server
Constantina's web server configuration manages the security of files hosted by
your site. By default, Constantina assumes that any dynamic content it serves
will be protected by an authentication step. So if your site is a basic blog,
and doesn't require authentication for viewers to see content, you'll need to
configure the web server to route around Constantina's protection logic.


### Filesystem Structure Overview
Assuming the default path for where Constantina web files are stored, your
web folders will look like this:

 * `/var/www/constantina/default/`
   * **`public/`** - _The web root folder_
     * `images/` - _Resources and self-hosted images for your site_
     * `medusa/`
       * `news/` - _Blog entries_
       * `pictures/` - _Randomly inserted pictures into the Blog feed_
       * __<...>__
     * `constantina.js`
     * `themes/`
       * `winflat.evergreen/`
       * __<...>__


### Webserver Configuration Strategies

#### UWSGI and Nginx on a Private Server
Constantina strongly recommends using Nginx as the forward-facing web server,
and UWSGI for the application server. It has the best performance and
flexibility of all the configuration strategies presented. This setup is 
shown in the `config/webservers/nginx-uwsgi-blog.conf` file.

Constantina itself will only respond to requests without _any_ provided URI
path (`location = /`). All other requests are assumed to be for static files.

`/etc/nginx/sites-available/constantina`:
```
server {
	<...>
	      # Webserver root, for which all locations are underneath
        # unless another location specifies a different one!
        root    /var/www/constantina/default/public;

        location = / {
                uwsgi_pass      localhost:9090;
                uwsgi_param     INSTANCE default;
                include         uwsgi_params;
        }
	<...>
```

`uwsgi.constantina.ini`:
```
[uwsgi]
socket       = localhost:9090
plugin       = python35
module       = constantina.constantina
processes    = 3
procname     = constantina-default
chdir        = /var/www/constantina/default/public
max-requests = 5
master
```

##### Running the Server
This will vary based on your OS packaging. The Debian/Ubuntu convention: your Nginx
.conf file must be symlinked into `/etc/nginx/sites-enabled`, and your UWSGI
configuration must be symlinked into `/etc/uwsgi/apps-enabled`. If these files
exist, then you can start the Constantina web and app servers with:

`systemctl start uwsgi nginx`

Logs will appear in `/var/log/nginx/` and `/var/log/uwsgi/app/constantina-default.log`.


#### Apache and mod_cgi, Shared Hosting
For those of you on shared hosting, Constantina will run behind `mod_cgi`
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

This strategy is ''extremely slow performing''. CGI applications must run and reload
all Python resources every time someone visits a site, and on embedded servers, this 
can add many seconds of latency to the initial page load!


#### VirtualEnv setup
Shared hosting environments may require you to bundle a bit of code together to support
your Python application. The `make-venv.sh` script will create a directory of
all the Python files and requirements that you need to run Constantina on another site.
Make a copy of this script named `make-yoursite-venv.sh` and modify the configuration
parameters to match your hosting situation.

**NOTE**: If you diverge from using `~/constantina` and instance name `default` for your 
virtualenv, you will need to add a configuration lookup path in the top of `shared.py` so 
that Constantina knows where to find its own `constantina.ini` file. This is a crucial
detail in shared hosting environments that don't allow you to specify an `INSTANCE` environment 
variable in configuration. Rather than fight your hosting provider, just use the default
virtualenv and instance settings.

Now that Constantina is a Python3 project, it takes a bit more effort to make VirtualEnv
environments that can be relocated to shared-hosting environments. This is because of 
dependencies like `pillow` which rely on `libjpeg` and other C libraries to be in specific
locations on the target server, which live in inconsistent paths on different Linux distributions. 
In this case, if you can't build the VirtualEnv on your server, I recommend making a Virtual 
Machine that matches your server's Linux distribution and platform (i686, x86_64). Once you do 
this, make sure the Python version exactly match the server OS you're working with, and that
`constantina.ini` and your `make-venv.sh` script has the exact filesystem paths you use on 
your server.
