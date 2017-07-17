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
In Constantina version 0.5.5, authentication tokens do not utilize any browser
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


### How Authentication Works
If Authentication is enabled, relevant settings for users' *session cookies*
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

Each signing and encryption key has a *two-day validity period* by default, and is 
*sunsetted* after one day. Sunsetting is where existing older tokens are still valid,
but their key is no longer used for encrypting or signing new tokens. The validity
and sunsetting timeframes are configurable in the `key_settings` section of `shadow.ini`.

Each instance of Constantina has an opaque *instance ID* that it adds to the name of the 
cookie. A given Constantina instance will only validate the cookie that contains the
correct instance ID in its cookie name. The opaque instance ID is stored in 
`constantina.ini` along with other instance information, like `hostname` and `port`.


### How Session Preferences Work
If Authentication is enabled, users will also get a *preferences cookie* describing
relevant settings for Constantina applications. The preferences cookie is a JWE-format
token, but managed separately from the session cookie. Although preferences details are
not sensitive themselves, the existence of plaintext preferences can give an
attacker context on whether the other application cookies are worth reviewing.

On the Constantina server, each user is assigned a *preferences keypair* containing one 
signing key and one encryption key, along with a *preferences id* for that keypair. None
of this preference data is sent to users, and this information is the only user preference
data stored on the server.

To prevent leaking what this cookie is used for, preference cookies names are given an
opaque *cookie id* that is the XOR of the Constantina instance id and the preferences id
of the keypair. This ties the preferences cookie to a specific instance of Constantina.
Unfortunately this also makes the preferences id easily reclaimable using the instance
id from the client's authorization cookie. However, the preferences id is just an opaque 
string, no client-accessible APIs take it as input, and the preferences id has no purpose
beyond identifying keyslots for validation and decryption of the user's preferences cookie.

Any time the user changes their preferences, the server reads the existing preferences
cookie details. Next, it generates a fresh preferences keypair, which invalidates any
unexpired old cookies from being useful. Lastly, the server writes the updated preferences
cookie, signed and encrypted by the fresh keypair.
