# Constantina
### A dynamic-content blog platform

## Upgrade Notes

### 0.6.0

TOWRITE: tweaks to make to config

### 0.5.6

The configuration files related to secrets were reorganized, so that file monitoring tools can more easily
track changes to secret preferences separately from changes to keys or passwords themselves. Contents from
`shadow.ini` were split off, with only password hashes remaining in this file. Server keys are now found in
`keys.ini`, and key algorithms and password length settings moved to `sensitive.ini`.

When upgrading, you'll likely need to move your settings to new sections by hand, as follows. Once you finish
these tasks, only the `[passwords]` section should remain in `shadow.ini`.

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
