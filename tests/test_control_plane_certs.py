from pathlib import Path
import sys
import datetime as dt
import ipaddress

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "Server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from projecta.control_plane.certs import ensure_cert


def test_ensure_cert_adds_key_identifiers_and_regenerates_legacy_chain(tmp_path):
    cert_path = tmp_path / "probe.crt"
    key_path = tmp_path / "probe.key"
    ca_cert_path = tmp_path / "probe_ca.crt"

    ensure_cert(cert_path, key_path, ca_cert_path)
    original_cert = cert_path.read_bytes()
    original_ca = ca_cert_path.read_bytes()

    assert original_cert.count(b"-----BEGIN CERTIFICATE-----") == 1

    server_cert = x509.load_pem_x509_certificate(original_cert)
    ca_cert = x509.load_pem_x509_certificate(original_ca)

    assert (
        server_cert.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier
        == ca_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    )

    now = dt.datetime.now(dt.timezone.utc)
    legacy_ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    legacy_server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    legacy_ca_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Project A Local Probe CA")])
    legacy_ca = (
        x509.CertificateBuilder()
        .subject_name(legacy_ca_subject)
        .issuer_name(legacy_ca_subject)
        .public_key(legacy_ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(legacy_ca_key, hashes.SHA256())
    )
    legacy_server = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")]))
        .issuer_name(legacy_ca.subject)
        .public_key(legacy_server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(legacy_ca_key, hashes.SHA256())
    )
    legacy_server_pem = legacy_server.public_bytes(serialization.Encoding.PEM)
    legacy_ca_pem = legacy_ca.public_bytes(serialization.Encoding.PEM)
    legacy_key_pem = legacy_server_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    cert_path.write_bytes(legacy_server_pem + legacy_ca_pem)
    key_path.write_bytes(legacy_key_pem)
    ca_cert_path.write_bytes(legacy_ca_pem)

    ensure_cert(cert_path, key_path, ca_cert_path)

    assert cert_path.read_bytes() != legacy_server_pem + legacy_ca_pem
    assert ca_cert_path.read_bytes() != legacy_ca_pem
    assert cert_path.read_bytes().count(b"-----BEGIN CERTIFICATE-----") == 1
    regenerated_server = x509.load_pem_x509_certificate(cert_path.read_bytes())
    regenerated_ca = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
    assert (
        regenerated_server.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier
        == regenerated_ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    )
