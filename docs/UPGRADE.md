# Constantina
### A dynamic-content blog platform

## Upgrade Notes

### 0.6.0

#### Internationalization Support

Constantina migrated to Python 3 for internationalization purposes. Be prepared to reinstall all dependencies and/or create a new *virtualenv*. I've been testing with Python 3.5 found on the latest Debian stable. To prevent *mojibake* from appearing on your existing Constantina feed, you need the latest version of the Constantina themes, which include HTML meta-tags to force browsers to display UTF-8 content. For existing admins using the default themes, install with the `--upgrade` option rather than just `--scriptonly`.

If you're creating a new Python 3 *virtualenv* for Constantina, the `make-env.sh` script may fail if there are stale `build/` and `*.egg-info` directories lying around, so delete those.


#### Rebuild Search Indexing

The content hosted on codaworry.com will have both English and Japanese-language content, and as a result I changed the tokenization strategy for the Whoosh search-indexing to support Japanese words and characters. As a result, the indexing process became case-sensitive, and I had to translate all searches and indexed content to lowercase words to fix this.

While old indexes will appear to work, there will be errors with searching for content with uppercase letters until you remove the old indexes and let them regenerate. If Constantina is installed in its standard path without a special instance name, removing the indexes looks like:

```
cd /var/www/constantina/default/private/index
rm MAIN* _MAIN*
```

On slower servers, the reindexing process may cause HTTP 504 timeouts, as the search indexing does not occur until an initial search request is made. While indexes are being generated, search requests will return HTTP 502. A future version of Constantina might do index generation at server-start time instead of at request time, to make this less obvious or painful to users.


### 0.5.6

The configuration files related to secrets were reorganized, so that file monitoring tools can more easily track changes to secret preferences separately from changes to keys or passwords themselves. Contents from `shadow.ini` were split off, with only password hashes remaining in this file. Server keys are now found in `keys.ini`, and key algorithms and password length settings moved to `sensitive.ini`.

When upgrading, you'll likely need to move your settings to new sections by hand, as follows. Once you finish these tasks, only the `[passwords]` section should remain in `shadow.ini`.

 * `shadow.ini [defaults]`:
   * `charset` => `sensitive.ini [accounts]`
   * `user_length` => `sensitive.ini [accounts]`
   * `password_length` => `sensitive.ini [accounts]`
   * `key_format` => `sensitive.ini [key_defaults]`
   * `key_size` => `sensitive.ini [key_defaults]`
   * `signing_algorithm` => `sensitive.ini [key_defaults]`
   * `encryption_algorithm` => `sensitive.ini [key_defaults]`
   * `encryption_mode` => `sensitive.ini [key_defaults]`
   * `subject_id` => `sensitive.ini [key_defaults]`
 * `shadow.ini [key_settings]`:
   * `lifetime` => `sensitive.ini [key_defaults]`
   * `sunset` => `sensitive.ini [key_defaults]`
 * `shadow.ini [argon2]` => `sensitive.ini [argon2]`
 * `shadow.ini [encrypt_*]` => `keys.ini [encrypt_*]`
 * `shadow.ini [sign_*]` => `keys.ini [sign_*]`

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
