# Constantina
### A dynamic-content blog platform

## Security
Software has low marginal costs for copying or deploying, but it tends to spoil 
without regular maintenance and security reviews of its code and libraries.
While my peers have cautioned me on writing *yet another* blog or web forum,
I feel this is an opportunity to own the software and security risks, so that
I can support and build a strong Internet community outside the standard
*user is product* channels.

This is an evolving document on Constantina's threat model, authentication,
security hardening, and known weaknesses.


## Known Weaknesses
In Constantina version 0.5.0, authentication tokens do not utilize any browser
identification strategies. This means they can be stolen and used on other systems.
This will be rectified prior to *Zoo*'s release.

Constantina currently lacks support for stronger or secondary authentication measures
like U2F, client certificates, or two-factor services.

The audit logging story for Constantina is not well-defined yet.


## Threat Modelling
The *Medusa* blog is most likely a publicly-visible service. The main threats to the
blog are DoS attacks to prevent your writing from being published to the world, or an
attacker using your site to distribute malware.

The *Zoo* forum has a similar threat model to other communications services. You want
confidentiality between users, non-repudiability that a user sent a message, and strong 
protections from misuse by attackers or unregistered users. The most damaging misuse I
can think of involves impersonating a trusted user or an admin, in order to compel or
gain sensitive information from users.

While *Dracula* hasn't been written yet, the e-mail threat model is largely centered
around the practical unavailability of verifiable identity information that guarantees
someone was the actual originator of a given e-mail message. It's likely that *Dracula*
will employ e-mail source whitelisting, and that initial versions will utilize local
IMAP/SMTP mailboxes and relays, similar to many forum's PM systems, but implemented
using standard e-mail protocols.


## Security Hardening

### 0.5.5: Authorization Models
Prior to *Zoo*'s release, a mechanism for files being accessible by a single user will
become necessary. User settings should remain private and unmodifiable by other users.

### 0.5.0: Authentication, IDOR Folder Shadowing, Directory Traversal Prevention
Constantina authentication appears in a testing configuration in 0.5.0. When converting
Constantina to using authentication, many supporting adjustments were necessary, as it
was trivial to directly link to the file paths for content that should have been
protected by the authentication form.

In order to force resources to remain private unless an authentication token is present,
Constantina started using a `private` folder for all dynamic content. The `private`
folder shadows the webserver root `public` folder. In other words, if a non-existent 
file is requested in the `public` folder, it will be served from the `private` folder as
long as a valid signed authentication token is provided.

With directory shadowing, it quickly became clear that you could provide paths to arbitrary
files on the filesystem that were world-writable. A `safe_path` function was written that
returns False for any folders that have directory traversing slashes or dots in them.


## Authentication
**Constantina Authentication is currently a work in progress, and is documented
for both testing and for input from peers.**


### Enabling Authentication and Configuring Accounts 
Constantina supports username and password-based authentication in version 
0.5.0, but there are no enrollment flows through the web interface yet.
However, a Python CLI script called `constantina_configure.py` lets you 
configure Constantina users.

**NOTE**: To make sure user ownership parameters for the config files don't get 
changed, run `constantina_configure.py` as the webserver's user account. 
This means you'll prefix it with `sudo -u www-data`.

To create a user and be interactively prompted for a new password:
`constantina_configure.py -a <login_name>`

To create a user and set an initial password in one step:
`constantina_configure.py -a <login_name> -p <initial_password>`

Enabling authentication in Constantina is a matter of setting `authentication`
to `forum` in your instance's `constantina.ini`.


### How Authentication and Sessions Work
If Authentication is enabled, relevant settings for users and session cookies
will appear in your instance's `/etc/constantina/<instance>/shadow.ini` file.

On the backend, Constantina uses *Argon2* password hashing for modern and 
tunable security of sensitive password hashes. All aspects of the Argon 
hashing algorithm are configurable in the `shadow.ini` file, including:

 * `v`: The version of the *Argon2* hash format (*19 is fine*)
 * `m`: The memory cost of checking a hash, in kilobytes
 * `t`: The time cost of checking a hash, in hash-iterations
 * `p`: The parallelization parameter (set based on your CPU/thread count)

Session cookies are JWE tokens, a format for encrypted JSON data. Inside
the JWE is a signed JWT that indicates a user, instance, and validity period.
The `shadow.ini` file, after a user first loads Constantina in a browser, contains
two encryption keys and two signing keys using the HMAC-SHA256 algorithm. One key
is labelled "current" and the other is labelled "last".

Each signing and encryption key has a two-day validity period by default, and is 
sunsetted after one day. Sunsetting is where existing older tokens are still valid,
but the key is no longer used for encrypting or signing new tokens. The validity
and sunsetting timeframes are configurable in the `key_settings` section of `shadow.ini`.

Each instance of Constantina has an opaque ID that it addes to its JWE tokens. A
given instance will only validate the cookie that contains the correct opaque ID in
its cookie name. The opaque instance ID is stored in `constantina.ini` along with 
the other `hostname` and `port` information.
