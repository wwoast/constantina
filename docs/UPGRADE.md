# Constantina
### A dynamic-content blog platform

## Upgrade Notes

### 0.5.6

The configuration files related to secrets were reorganized, so that file monitoring tools can more easily
track changes to sensitive keys and passwords separately from the preferences that govern thoes secrets.
Contents from `shadow.ini` were split off, with only password hashes remaining in this file. Server keys
are now found in `keys.ini`, and key algorithms and password length settings moved to `sensitive.ini`.

### 0.5.5

The `X-Sendfile` trampolining support involved overhauling the Nginx and Apache configurations for Constantina. `INSTALL.md` describes the current configuration setup that works for Constantina going forward. 

### 0.5.3

When upgrading, you may need to manually add settings or files to avoid runtime issues:

 * `zoo.ini` into your local settings folder
 * `max_items_per_page = 100` to `constantina.ini`

### 0.5.2

The images directory has moved, since these files may be contextually sensitive to the text entries in the Medusa app, which can be protected by authentication.

When doing a `--upgrade`, Constantina will break unless you move the `public/images` directory to `private/images`. Constantina also requires that the private folder be on the same path-depth as the public folder. In other words, you need a `private` folder or a symlink to your `private` folder in the same parent folder as the web server's actual `public` webroot.

When upgrading, you may need to manually copy the `html/private/medusa/headers/empty` file into your corresponding folder. Otherwise it will only land if you do a full non-`--upgrade` installation, which could overwrite or add files to your private folders.
