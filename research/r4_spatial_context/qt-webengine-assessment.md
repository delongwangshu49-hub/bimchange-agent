# Qt WebEngine product-candidate assessment

Decision: `CONDITIONALLY_PERMITTED_FOR_ISOLATED_PRODUCT_CANDIDATE`

The standalone R4 research gate passed, so an isolated desktop vertical slice
may now be built. This is not permission to alter the stable R3 Schema, dirty
main, GitHub, or the v0.9.0 release.

## Measured dependency impact

The existing v0.9.0 source uses `PySide6-Essentials==6.11.1`. Qt WebEngine is
provided by `PySide6-Addons==6.11.1`.

On the frozen Windows/Python 3.13 host, the official wheel audit measured:

| Item | Measured bytes |
|---|---:|
| PySide6-Addons 6.11.1 wheel | 168,816,308 |
| Complete uncompressed Addons wheel | 457,910,349 |
| `Qt6WebEngineCore.dll` uncompressed | 204,828,984 |

The wheel is monolithic and includes many unrelated Qt Addons, so the final
PyInstaller and installer delta must be measured rather than inferred from the
wheel total. The current 65 MB installer baseline is expected to increase
materially.

## License gate

Qt's official documentation states that Qt-specific WebEngine parts are
available under LGPLv3/GPL/commercial terms, while the bundled Chromium portion
contains multiple third-party licenses with the most restrictive identified by
Qt as LGPLv2.1. Any distributable candidate must extend the current third-party
notices and license bundle to include the exact WebEngine/Chromium materials
shipped by PySide6. No release is permitted from a development import test.

## Security and privacy design

The candidate must:

- serve only generated viewer-bundle files from an ephemeral loopback origin;
- use a random per-session URL token and no directory listing;
- attach an off-the-record `QWebEngineProfile`;
- block every request outside the exact loopback origin;
- reject navigation, popups, downloads, permissions, and external schemes;
- keep IFC conversion in the Python process and never expose IFC binaries to
  JavaScript;
- preserve the deterministic Change Record as the fact source;
- stop the local server and discard its temporary bundle when the window closes.

## Candidate budgets

These are product-candidate gates, not stable promises:

- added installed footprint: measure and report; fail if above 600 MiB;
- portable ZIP: fail if above 350 MiB;
- installer: fail if above 250 MiB;
- first local scene visible: at most 5 seconds on the recorded host;
- report-row selection to highlighted target: at most 2 seconds for the
  synthetic acceptance pair;
- external requests, uploads, model/API calls, and privacy violations: zero.

If WebEngine packaging breaches these budgets or license material cannot be
audited completely, the desktop candidate fails closed and the standalone local
viewer remains the only passed R4 result.

## Recorded private-candidate result

The isolated Windows product candidate passed the source, desktop, packaging,
and privacy gates on 2026-08-25, but it remains blocked from distribution by the
license-material gate.

| Item | Recorded result |
|---|---:|
| Product regression | 50 passed, 2 opt-in WebEngine tests skipped |
| R4 research unittest wrapper | 2 passed |
| Native WebEngine integration | 2 passed in 4.644 s |
| Portable ZIP | 254,390,115 bytes (242.61 MiB) |
| Unpacked portable directory | 627,954,526 bytes (598.86 MiB) |
| Files in portable directory | 3,719 |
| ZIP SHA-256 | `14cb219ff42f3484ab516fbba9cb19054ef94e140809f5ef7ecc3acc60fc91f8` |
| Private installer | 162,224,759 bytes (154.71 MiB) |
| Installer SHA-256 | `cf9f88599a395b3dd3a84f36633ae15162f11ecb2bea8995b3680ece134d732e` |

PyInstaller initially produced a 715,428,558-byte (682.29 MiB) directory. The
only removed runtime payloads were
`qtwebengine_devtools_resources.pak` and
`qtwebengine_devtools_resources.debug.pak`, totalling 87,453,906 bytes. The R4
viewer never enables remote debugging or DevTools. A second isolated build
reduced the directory below the 600 MiB gate. Native tests were then rerun with
`QTWEBENGINE_RESOURCES_PATH` and `QTWEBENGINE_LOCALES_PATH` pointing directly
at that trimmed packaged resource tree: the off-the-record viewer loaded the
correct target and bounded context, the report row resolved the same GlobalId,
all HTTP requests used the random token prefix, and non-allowlisted requests
were blocked.

The packaged main window also launched successfully. This does not replace the
native scene test: the two results are recorded separately so that a successful
application boot is not misreported as viewer proof.

The final package also removes only IfcOpenShell's generated
`simple_spf/fixtures` directory, following the existing v0.9.0 packaging gate.
Its only remaining IFC files are the three runtime Pset schemas. Binary scans
found no workspace path or user identifier. One broad API-key regular
expression matched random bytes inside `Qt6Quick3DHelpersImpl.dll`; the packaged
file is byte-identical to the installed PySide6 dependency and has a valid The
Qt Company Oy signature, so it is recorded as a vendor-binary false positive,
not a credential.

## Distribution decision

Status: `PRIVATE_CANDIDATE_PASS_PUBLIC_DISTRIBUTION_BLOCKED`.

The PySide6-Addons wheel audit exposed only
`pyside6_addons-6.11.1.dist-info/licenses/LicenseRef-Qt-Commercial.txt` as a
direct license file. That is not a complete copyable inventory for the exact Qt
WebEngine/Chromium payload included by PyInstaller. The candidate therefore
contains an explicit `R4-NOT-FOR-DISTRIBUTION.txt` marker and must not be
uploaded, released, or presented as stable product support until the exact
third-party notices, source/offer obligations, and LGPL replacement rights are
verified and bundled. After explicit user authorization, an unsigned installer
was built only for local manual validation. It uses a separate AppId and install
identity, carries the `NOT FOR DISTRIBUTION` marker, and does not represent a
public-distribution decision. Its isolated smoke test installed the candidate,
verified all 3,719 payload hashes, kept the executable running for eight
seconds, and uninstalled it successfully.
