#!/usr/bin/env python3
"""Create a dedicated local ComPet signing identity. Requires explicit user approval."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

NAME = 'ComPet Local Development'


def run(args, label):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        # Never include commands/arguments here: import arguments contain a temporary password.
        detail = result.stderr.strip()
        for index, value in enumerate(args[:-1]):
            if value == '-P':
                detail = detail.replace(args[index + 1], '<redacted>')
        raise RuntimeError(f'{label} failed (exit {result.returncode}): {detail}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approve-keychain-changes', action='store_true',
                        help='Confirm creation/import and user-domain trust for code signing only.')
    args = parser.parse_args()
    if not args.approve_keychain_changes:
        parser.error('Explicit approval is required: --approve-keychain-changes')
    os.umask(0o077)
    keychain = run(['security','default-keychain','-d','user'], 'Finding login keychain').strip().strip('"')
    existing = subprocess.run(['security','find-certificate','-c',NAME,'-p',keychain], capture_output=True, text=True)
    if existing.returncode == 0:
        raise RuntimeError('The dedicated certificate already exists; inspect it instead of replacing it.')
    openssl = shutil.which('openssl')
    if not openssl:
        raise RuntimeError('OpenSSL is required.')
    with tempfile.TemporaryDirectory(prefix='compet-signing-') as directory:
        base=Path(directory)
        key,cert,der,p12,password=(base/name for name in ['key.pem','certificate.pem','certificate.der','identity.p12','password'])
        secret=secrets.token_urlsafe(32)
        password.write_text(secret)
        run([openssl,'req','-x509','-newkey','rsa:3072','-nodes','-days','3650',
             '-subj','/CN='+NAME,'-keyout',str(key),'-out',str(cert),
             '-addext','basicConstraints=critical,CA:FALSE',
             '-addext','keyUsage=critical,digitalSignature',
             '-addext','extendedKeyUsage=critical,codeSigning'], 'Generating signing identity')
        run([openssl,'x509','-in',str(cert),'-outform','DER','-out',str(der)], 'Reading public certificate')
        fingerprint=hashlib.sha1(der.read_bytes()).hexdigest().upper()
        run([openssl,'pkcs12','-export','-name',NAME,'-inkey',str(key),'-in',str(cert),
             '-out',str(p12),'-passout','file:'+str(password),
             '-keypbe','PBE-SHA1-3DES','-certpbe','PBE-SHA1-3DES','-macalg','sha1'], 'Preparing protected import')
        run(['security','import',str(p12),'-k',keychain,'-P',secret,'-T','/usr/bin/codesign'], 'Importing into login keychain')
        receipt=Path.home()/'.config/compet-signing/identity.json'
        receipt.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        receipt.write_text(json.dumps({'name':NAME,'sha1':fingerprint,'keychain':keychain,
                                      'trust_policy':'codeSign only','bundle_identifier':'Compet-V3'},indent=2)+'\n')
        # No -d flag: user trust domain only. No SSL/basic/X.509 trust policy is added.
        run(['security','add-trusted-cert','-r','trustRoot','-p','codeSign','-k',keychain,str(cert)], 'Enabling code-signing-only user trust')
        identities=run(['security','find-identity','-v','-p','codesigning',keychain], 'Verifying signing identity')
        if fingerprint not in identities:
            raise RuntimeError('The new identity is not available for code signing; inspect Keychain Access.')
    print('Created dedicated local code-signing identity:',NAME)
    print('Public certificate SHA-1:',fingerprint)
    print('Private key remains in the login keychain; temporary exports were removed.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError,OSError) as error:
        raise SystemExit(str(error))
