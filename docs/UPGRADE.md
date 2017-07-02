# Constantina
### A dynamic-content blog platform

## Upgrade Notes

### 0.5.3

When upgrading, you may need to manually add settings or files to avoid runtime issues:

 * `zoo.ini` into your local settings folder
 * `max_items_per_page = 100` to `constantina.ini`

### 0.5.2

The images directory has moved, since these files may be contextually sensitive to the text entries in the Medusa app, which can be protected by authentication.

When doing a `--upgrade`, Constantina will break unless you move the `public/images` directory to `private/images`. Constantina also requires that the private folder be on the same path-depth as the public folder. In other words, you need a `private` folder or a symlink to your `private` folder in the same parent folder as the web server's actual `public` webroot.

When upgrading, you may need to manually copy the `html/private/medusa/headers/empty` file into your corresponding folder. Otherwise it will only land if you do a full non-`--upgrade` installation, which could overwrite or add files to your private folders.
