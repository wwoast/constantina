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
   * `argon2_cffi` and `argon2pure` for password hashing
   * `jwcrypto` for managing JWT and JWE session token formats
   * `defusedxml` for occasions where you need to parse HTML files
   * `mutagen` for MP3 length parsing
   * `passlib` as a wrapper for password hashing
   * `pillow` for image operations. Successor to the older `PIL`
   * `python-magic` for file type checks
   * `whoosh` for reverse-index word searching
   * `wsgiref` if you need to use Apache and `mod_cgi`
 * Second-order dependencies for the above libraries include:
   * `appdirs`, `pyparsing`, `idna`, `asn1crypto`, and `cryptography` 


### Running the Installer
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


### Instances
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
     * `constantina.js`
     * `themes/`
       * `winflat.evergreen/`
       * __<...>__
  * **`private/`** - _Content behind authentication_
    * `images/` - _Resources and self-hosted images for your site_
    * `medusa/`
      * `news/` - _Blog entries_
      * `pictures/` - _Randomly inserted pictures into the Blog feed_
      * __<...>__
    * `zoo/`
      * __<...>__

Constantina's webserver configuration is oriented around one major principle: As 
an authenticated user on Constantina, or as a content-writer, _the `public` and 
`private` directories should appear to be merged_. There are two strategies for 
doing this.

 * **Private/Secure**: Requests for `private/` files get directed through Constantina
   * Use this if you want a private blog or forum
 * **Public/Open**: The webserver redirects to `private/` files directly
   * Use this if you want a public site without user accounts or authentication

Regardless of Constantina's application config, either of these solutions will
work. Be aware that **using the Public/Open config makes your files
accessible to unauthenticated users, regardless of your Constantina settings**!


### Webserver Configuration Strategies

#### UWSGI and Nginx on a Private Server
Constantina strongly recommends using Nginx as the forward-facing web server,
and UWSGI for the application server. It has the best performance and
flexibility of all the configuration strategies presented.


##### Blog mode (no authentication)
This setup is shown in the `config/webservers/nginx-uwsgi-blog.conf` file.

If Constantina is a public blog, then chances are you don't want users to
authenticate. By configuring `images/` to use the private path as its root,
you "pretend" the private directory exists inside the public one. In
actuality, the basic public/private split is preserved, should you wish to 
enable authentication later on.

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
        
        location ~ ^/(images/.*|medusa/.*|zoo/.*)?$ {                                                               
                root /var/www/constantina/default/private;                                                          
        }
	<...>
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

##### Forum mode (authentication)
This setup is shown in the `config/webservers/nginx-uwsgi-forum.conf` file.

If a user has authenticated to Constantina, user requests for `images/file.jpg`
will have an `X-Sendfile` and `X-Accel-Redirect` header as part of their
response. This header is how Constantina instructs Nginx to fetch 
`private/images/file.jpg`, in response to the original `images/file.jpg`
request.

The `/private` location being marked as `internal` guarantees that Nginx will not
serve files out of this folder, without Constantina's `X-Accel-Redirect` header
giving it permission to do so.

`/etc/nginx/sites-available/constantina`:
```
server {
	<...>
	# Webserver root, for which all locations are underneath
        # unless another location specifies a different one!
        root    /var/www/constantina/default/public;

	location ~ ^/(images/.*|medusa/.*|zoo/.*)?$ {
                uwsgi_pass      localhost:9090;
                uwsgi_param     INSTANCE default;
                include         uwsgi_params;
        }

        location /private {
                internal;
                # /private is added to the end of this!
                root /var/www/constantina/default;
        }
        <...>        
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

##### Running the Server
This will vary based on your OS packaging. The Debian/Ubuntu convention: your Nginx
.conf file must be symlinked into `/etc/nginx/sites-enabled`, and your UWSGI
configuration must be symlinked into `/etc/uwsgi/apps-enabled`. If these files
exist, then you can start the Constantina server with:

`systemctl start uwsgi nginx`

Logs will appear in `/var/log/nginx/` and `/var/log/uwsgi/app/constantina-default.log`.


#### Apache and mod_cgi, Shared Hosting
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

This strategy is ''extremely slow performing''. CGI applications must run and reload
all Python resources every time someone visits a site, and on embedded servers, this 
can add many seconds of latency to the initial page load!

Additionally, Apache doesn't support `X-Sendfile` lookup paths as configuration in a
user-configurable `.htaccess` file. If your hosting provider won't configure the
proper `X-Sendfile` settings, then effectively **you have no way to protect your private
files behind authentication**. You can still use Constantina, but your forum's content
will be vulnerable to filename guessing by an attacker (the _Insecure Direct-Object Reference_
vulnerability).


#### VirtualEnv setup
Shared hosting environments may require you to bundle a bit of code together to support
your Python application. The `make-venv.sh` script will create a directory of
all the Python files and requirements that you need to run Constantina on another site.
You'll likely want to edit on the `constantina.ini` config paths and other directory paths
to match the specifics of where your server's Constantina files live.

**NOTE**: If you diverge from using `~/constantina` and instance name `default` for your 
virtualenv, you will need to add a configuration lookup path in the top of `shared.py` so 
that Constantina knows where to find its own `constantina.ini` file. This is a crucial
detail in shared hosting environments that don't allow you to specify an `INSTANCE` environment 
variable in configuration. Rather than fight your hosting provider, just use the default
virtualenv and instance settings.


#### Other Notes
Both the `blog` and `forum` webserver configs have special strategies to show a default
forum avatar if a user hasn't yet uploaded one. The ordering of paths in the Nginx configs
is important for that logic to function.
