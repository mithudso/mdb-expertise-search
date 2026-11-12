# Maintained-source coverage — 2026-11-12

This inventory separates frozen review inputs from later repair bytes and
additions. The final blind result is **BLIND-AUDIT-DISSENT**.

## Frozen denominators

Initial diagnostics covered 112 maintained targets: 109 external and 3 native
reports. Two extra archive/license reports are excluded from that denominator.
Gate 1 covered 129 unique files with 130 substantive reports across the changed
generator hash. Gate 2 completed 145/145 valid 15-pass reports and completed turns,
with zero frozen-source drift, missing/invalid reports or active readers.

The 145 legacy targets include 143 runtime/configuration/test records, one LICENSE
prose record and one auxiliary .gitkeep. Their prose/auxiliary status is explicit,
rather than a claim of 145 runtime-code audits. The original iteration-3
before-manifest has 146 records, including the then-absent core regression test.

The per-file contract is C1–C3, S1–S5, P1–P2, M1, intra-file M2, M4 and T1/T4
where applicable to tests. Repo M3/T2/T3, cross-file M2 and test-performance
decisions are separate. Coverage accounting is not a CLEAN verdict.

Gate 2 contains 251 raw Medium+ rows (2 Critical, 26 High, 223 Medium) and 13
retained Low rows. The post-gate execution ledgers contain 252 corroborated rows:
243 Medium+ real manifestations, 1 Low observation, 6 duplicates, 2 blocked. Ordinary upstream helper/caller row
UPSTREAM-CI-F1 explains the extra execution row; it is not an extra blind report.
Rows, duplicates and shared/paired fix units are not independently unique bugs.
The original 244-real classification is preserved as history; native adjudication
now retains 243 Medium+ real manifestations plus 1 Low/bootstrap observation.
The static index pair repair remains implemented without inventing a prior
atomic-pair contract.

The original 5-iteration cap and 2 blind slots remain. Iterations 1/2 preceded
a96aee5; iteration 3 is focused post-gate repair/integration, not a new diagnostic
gate. The 2→4 gate-1 and 8 gate-2 allocation history, admitted dispatcher,
exclusive lock, original/partial raw events and source-hash receipts remain
retained. No 50-file limit or restarted collection changed the denominator.

## Protected/data exclusions

The historical 514 excluded records comprise 444 protected identities plus 70
generated, fixture, lockfile or binary records. Protected identities preserve
baseline hashes through metadata-only checks. Their bodies, customer paths and
vector values are not reproduced here; this census is neither source inspection
nor redistribution clearance. No node_modules, virtualenv, build output, model/
cache/store or customer research body enters the maintained-source audit.

Search/chunk/vector fixtures and all lint expectations remain unchanged. Exactly
four authorized optimizer expectations changed before a96aee5; post-gate work
changed none of the 49 ordinary expected-output fixtures. Production chunk_text
and _merge_tiny remain exact to 592db43 under KNOW-1855. No copied codec,
monkeypatch or alternate generator masks serialization drift. The four
representation defects remain blocked; schema-dependent advice retains prior
behavior because two ordinary expectations are outside the authorized scope.

## Legacy gate-2 frozen hash inventory

These identify the exact frozen inputs at checkpoint
a96aee5409964dbf45cdef0b18b6708970a53280. They do not assert that final repair
bytes are unchanged or received another 15-pass review.

| Legacy maintained target | Frozen gate-2 source SHA256 |
|---|---|
| `.editorconfig` | `fa4b659891b975ba2fe617ef5eaa16e2531060af5a8b5e225ac1dff58e99aebe` |
| `.env.example` | `fb7d988a9494e3e9f7b36b1f04e979453ff00254d8825cc2de674ba6096f50be` |
| `.gitattributes` | `6db1e9159c99b279343da4335721c03e1fd65a2fbbd3faf8de1e743a467b10be` |
| `.github/CODEOWNERS` | `57059c7b6958ecc7c9d73f2545410f39f4be601fd7b6211c0f7ece7d1c750c88` |
| `.github/dependabot.yml` | `d606f7d4723145bf563819dfbde97fdca4d03692cb18a1e11f302307a78a7ba5` |
| `.github/workflows/ci.yml` | `2afa93d13665254786202e6823316430fce94eec3fea0af460dfb785cad96aa8` |
| `.gitignore` | `0a064473eb248e2b9de07e6b87910a2021594d55f25b40a1866e3bb11204946b` |
| `.mcp.json` | `206d63b8302ae8a92d4ce3ae49dc446b6ca6a8a7a085ed4cb6ae211021f82a5c` |
| `.node-version` | `20d2add851bf39edcc6b5e830930f962db7e19dffa2cab8610eed551eda6c302` |
| `.vscode/extensions.json` | `f902659f9d871c088d9565db4b11b3547b5e3659a47d1deb7afca54e9b41b10a` |
| `.vscode/launch.json` | `4937b41004c717f321880d6663a221bc48bad7a7372b22df0c804910c6de2bae` |
| `.vscode/mcp.json` | `27f996232225e3802a6f6ff96249b181b6d4c13b031861a628450b512068671f` |
| `.vscode/settings.json` | `90185922fb1ce721d222511bae9477e6697e7efad55ac9d8b05433b4273ef40b` |
| `docs/archive/.gitkeep` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `editors/chrome/app.css` | `f083691c5a52e0006336cf824abb439e8d3e5ddbc19e85a3d235300892291039` |
| `editors/chrome/app.html` | `d9f0666a0dc86d30ff6040350dbd5006b6371325c4d3f5b104624c6cda14d908` |
| `editors/chrome/app.js` | `d4bbc3483240d710b505e14b7d9ae4552eaa7fbca495e43fdc55dc2bf2e0a2d0` |
| `editors/chrome/background.js` | `fd35d9cfcede085e74e5420b3bfe9bc7811d97df232c3a6e833fbc7c4b68a34a` |
| `editors/chrome/lib/analyze.js` | `bdc5bdfaba6f17ab37d7bf96e79d8438f1130397489661a975557f0689c00d99` |
| `editors/chrome/lib/autoupdate.js` | `8a4d512413f7f8f8de4d534c2fa1ca508b9608e90d0e88ccf800a2af3e9b76ff` |
| `editors/chrome/lib/capture.js` | `bc5973dfbe8c3bcd42d011e8cccb899cd96504caf16b320faf5a69a17c9ef7fc` |
| `editors/chrome/lib/docs.js` | `18b9958318b9fb7753086c6f0127e61ba154fd737fe6cd4144de375293c5ea28` |
| `editors/chrome/lib/normalize.js` | `8839d3ff858a78350505be56ea5a29cc5658679a7a3f5cae4dedf94e49f11721` |
| `editors/chrome/lib/operators.js` | `de3bcab2d070f03a40f20d1f405fdfaabd75be845180657a34735aa6e9be45cb` |
| `editors/chrome/lib/optimize.js` | `44eba4cb0752f50a5918c163d3b30f92a8f532d745c8cd6a518acb80ff858071` |
| `editors/chrome/lib/parser.js` | `d2879593931ee11a285bdc583ca26cf98e63fd9965bf65afcbdaa9966944849a` |
| `editors/chrome/lib/report.js` | `f213cc8603bb0cd3fe87da4746aa467c47523236113b97d86cd34491bbb61347` |
| `editors/chrome/lib/store.js` | `d169f5d81257aacd68957b403af0f4055caa20041bd0a5eb01576c90aa35130f` |
| `editors/chrome/lib/textsearch.js` | `205d8177b8a7e51af77c0b80f68d6dfc6099fb4d1f1eb4fa88b6200dc29a3374` |
| `editors/chrome/lib/ui.js` | `eb78c4d443e79108b35ee93714bbcc8eef6f41497137853a91ec0efd79b2b4e2` |
| `editors/chrome/lib/unicode61.js` | `a7a103d9726fcc3a279538f094773d442b9f7d3192a0f908f1712a7fcd96ea73` |
| `editors/chrome/manifest.json` | `5ad47b710c091cab6f9877640d5a9a4015085d48c35b7bca85b735f2f3a0655e` |
| `editors/chrome/package.json` | `0dd44d255401b8dd7a506dc9f66c87e181c37cc1f8c99bd2e160a02819393611` |
| `editors/chrome/popup.css` | `405a9962076bb63d7f2113d9ad2c5652ab7addec3be79992522f23cbbb17e23d` |
| `editors/chrome/popup.html` | `12154413c3d67abff21206f4c4a6893ad98f26a030fa30aa44cf42ed29b3cc1f` |
| `editors/chrome/popup.js` | `51a4c436245e4ad5c80eb3213cd71c24228c2705cbcca86b40f93bc6af5b6bc0` |
| `editors/chrome/test/autoupdate.test.mjs` | `0a89fc0ed2ad57315a307685d53511c4d4b9ef874155a50e532bb1d18009fe64` |
| `editors/chrome/test/batch.mjs` | `f44c9fc3807b8fcc88967b12f3541b8b300b50d9657c33fc092057eadba2e43d` |
| `editors/chrome/test/browser-context.mjs` | `cf1c2ffa6274b9aa95a5ef43dea07939fe1508cc2a1a37b2efd207f664e0cb20` |
| `editors/chrome/test/browser-context.test.mjs` | `c2ee2d7af7663ab35aa229b03e414c7b449f9f648a5510a7cf586f3bf1b310dc` |
| `editors/chrome/test/debug-app.mjs` | `05e3b029be067cf638548cf584d87464d00880c58cdf668e21377d0c72363145` |
| `editors/chrome/test/dom-fixture.mjs` | `2edc52fb9f960461360a700ef0c24ed5f1d46bdf78d202a44702dad62f6e4183` |
| `editors/chrome/test/e2e.mjs` | `fb7de8331c11a2334dc1b033bef92fa9b2e1399c105e3c883c90ff785f50a0ea` |
| `editors/chrome/test/integrity.test.mjs` | `e5fe6f912be2ddc442b8166d33bd6f1b795aff30ad461ae426e3ffa6ef153c3d` |
| `editors/chrome/test/language-boundaries.test.mjs` | `0016de236ee5d2ec19b12899405fe78d7e4ad1bc9b83a78597aef495252c6d22` |
| `editors/chrome/test/lint-batch.mjs` | `fbfe0de8ee5aca7180af64fa7f1fdf28bce02cec89890127df312fcee2cb003c` |
| `editors/chrome/test/lint-parity.test.mjs` | `51f1ae62c05fbc6503babe7c68707783464a3b1d0c369681a14e60b51c05d85a` |
| `editors/chrome/test/normalization-boundaries.test.mjs` | `58bbf5ae34828062ef635c4682e846c20fb5e5b690b2bbc2c5410643cd88e616` |
| `editors/chrome/test/optimizer-boundaries.test.mjs` | `a274381e93225a5a93104186c2a09e6bab4ef8466e16331f68ec7e2ce10ec1fb` |
| `editors/chrome/test/page-races.test.mjs` | `501a950f048591c80f4db29936e36a3eccaf1e8707c00397797b4dd0864343df` |
| `editors/chrome/test/parity.test.mjs` | `7fe8fbee82f091fa28194743888aedfb355f0b64983f86b24ced2f5cc28e4a51` |
| `editors/chrome/test/rendering.test.mjs` | `8640611463d5cf428726023764b2a6f8c2caea9d9f5d69c312dde3eae03a9751` |
| `editors/chrome/test/run-tests.mjs` | `918957b93f088c3a6e6decc1696118c66e46f65ccd991552cfae2a17b7255c23` |
| `editors/chrome/test/search-batch.mjs` | `4b7e6caed031bab86b5828e82172d00bcfd42804963f3d656bc80a908eada905` |
| `editors/chrome/test/search-parity.test.mjs` | `edf7491642505cde0de183c3c5c8891526c026eaa727cb5f9ad1812bc3db9faa` |
| `editors/chrome/test/search-rendering-boundaries.test.mjs` | `dfdf244d6b73e228713138d07f149b336582a2fb6322ce96ff1bbb89ee2a3223` |
| `editors/chrome/test/ui-boundaries.test.mjs` | `ed0eed1942684aa9c91f810379398bcd2f7cbfddfa91a73b29f7dd58df0f8e37` |
| `editors/chrome/test/ui.test.mjs` | `f3654380fcf4a4d79d7212bd98fb42bcd77b4c0def18f1d73a09bd74cef476ed` |
| `editors/helix-languages.toml` | `f5c476810f8178c1a0d0b0d03a163e111475610f51eb6f3a0ce5b68bc3bc8cf3` |
| `editors/neovim.lua` | `b6132005e54b80f97f7542ea17699222f2c90938ddd1a9edc7d8cdaf07b8a983` |
| `editors/vscode/.vscodeignore` | `759fb32b972bdfc00a782c96dd5c48b13febd040125f4d99dc32e563c91d9cef` |
| `editors/vscode/LICENSE` | `b9d887fa367fbe881d916d29a3dae2d755ec96f582425673012f82f217cc70c5` |
| `editors/vscode/extension.js` | `4ae8bc61bf334817ce4b4964b1de55f6c3a15dae3f49db9ad56d0164d986efb4` |
| `editors/vscode/language-configuration.json` | `0b6b06557de680d55b5cdf1e30a864483767400671697092c18ac6884628a651` |
| `editors/vscode/package.json` | `fb5e8159d1abd9ebf15ba9e4924f72000ad92b55837bbeab6c08b26694ea58e2` |
| `editors/vscode/server-path.js` | `9092395c6da6aabaaf5b92c9d8306a1a48993223daa4a23a5724848761c7878d` |
| `editors/vscode/syntaxes/mql.tmLanguage.json` | `a15167224f4ce536db7529401703ff030c325809ad21b52a05c6964267f89513` |
| `editors/vscode/test/server-path.test.js` | `399fbdeefdfdf25b063545f90477b3afdbf02cb14e02538a3171e31c3265b1c1` |
| `examples/orders.mql` | `71b2160dd9fd8baf2193418670755b591dd6b3b29a87b1e5d2cf757123204893` |
| `examples/slow-queries.mql` | `5ac151fc40a7f943a9b79a928e23db13855ce5cb409140998142b30d6731c8c6` |
| `mdbx/__init__.py` | `a8503c63782616400e339ff9fbc9e6cdaf0f56e01b48d11d5f27a32069d85413` |
| `mdbx/cli.py` | `ab3c148a234cfb5b339b78752644ff36f44e4b632d88adcf45103cdb95ffcdd3` |
| `mdbx/corpus.py` | `7592d3dc6144427d4d609d3264b06346d40a37ad712daf0b1425eab223c31e3d` |
| `mdbx/embed.py` | `cdb35208354805cb341dd221d6a0339633dddea0fde7d8bcdc1b49b984c44452` |
| `mdbx/embed_onnx.py` | `f1a633e6eaa967a11e20244692ab6cd41b73176ab4b22fe2a3cd29245a68d7a8` |
| `mdbx/index.py` | `33882c802aeb99ac09363255c327eda44c9cfdc12b51bed4afaa856bf16ce022` |
| `mdbx/mcp_server.py` | `70eb5d528c36a780cfa12e13bb8a76db7c4d9637e0c4e0165cab4e04097fdd4e` |
| `mdbx/mql/__init__.py` | `06b44fc0495f43e46f20480f7fa826daf38776246f823753b7d9f8fc76dc9fe6` |
| `mdbx/mql/analyze.py` | `4f815b7701f630e84a6d45f053753353c5c9929e2b50f73e7ac082343981894f` |
| `mdbx/mql/features.py` | `0d4bfd52f1dc46001efc795d1f82a9f3b432921ce99bb595b1cd5a82938e5e9e` |
| `mdbx/mql/normalize.py` | `67acb6a35010e218e73453177134055e30eeb1ceeafca163b661602fab7a5f96` |
| `mdbx/mql/operators.py` | `6c9efd4af3989a4bed28f8d4fc7eb9bf4023af5d9d4b6c3767ec56eea7715aa8` |
| `mdbx/mql/optimize.py` | `9621430c2e3289e786d5ec21de5ddc3199c8883bbcbc3e38925f4f061aa53cfb` |
| `mdbx/mql/parser.py` | `4d76edae10a7d8729a650ef1dd9f179874dabd0d8a35148d38a08b469b5e338c` |
| `mdbx/mql/server.py` | `c629f1b3f93a139cb616e8a1dd25a5a26c57f16e1d2990d3c427ad4e3c9460fe` |
| `mdbx/providers.py` | `983f6a5f0c84f95f988d90041e30308c8dd62362c507f7e0382ef7d1816fa6dc` |
| `mdbx/recipes.py` | `40696e553ae5349ad5eb3d60a6e507c319e4bcf579fecb5b8e0d3332ed509d6f` |
| `mdbx/safety.py` | `85c319f3ebf61e8e40efed52cd6e9ca3e601fccc03c0c6c1812f21bba078bb5d` |
| `mdbx/search.py` | `c095ba1b7e7f08607edafbb133943c038b951a0f6fe04ee1218fa23fb4ab6450` |
| `mdbx/tui.py` | `aae16a04218f93fe06d78169ac03e0695a917e761462ef2b4d47fdf6e07ecf9d` |
| `mdbx/unicode61.py` | `8d60c69daf24ee08c4b07ed977cb8b550655f57453cdb27f996a2924175f1342` |
| `mdbx/webexport.py` | `a4fb86d0f15943c6f45aeff90fd583909bc35bbdb86f06c06616fab923686acf` |
| `pyproject.toml` | `c0e8e54d87e5af9ad93a5505a43e22a08938ba6b11330ea06332528b16626b58` |
| `scripts/check_chrome_doc_links.py` | `603481e505a1b29cf9181a28345e8b6eafa1494c9a9da72294274034d8d1c677` |
| `scripts/check_doc_indexes.py` | `93297f73bdb2eea076e23fb1373bd4fa28f777d5d400b175723de7375bb7f2d5` |
| `scripts/chrome_extension_autoupdate.py` | `86f1f9ab7cfaa9315abab5e9936705d04a746e9959ff8d10ef827896d5bd2fba` |
| `scripts/corpus_autoupdate.py` | `8c35b0384e3a60ab6daf178b440a38350bb7d223f36dddb98492d09acc30e205` |
| `scripts/gen_chrome_operators.py` | `f8d602292c4e67462f4dfef7279812ce437b7e7637871f7754a5fd3c9ba2ecd1` |
| `scripts/gen_file_index.py` | `d94f8af87c23b7eaa077f7a0037c8a9e7cab35f1129595fedf996fa210a76e42` |
| `scripts/gen_lint_golden.py` | `c2834cbc50fd57cc3ac982874de6a231c94f6ca1632f05951fb951190fc4ce62` |
| `scripts/gen_optimizer_golden.py` | `fcf74531301bae7557b61814c83853bc24941491664872efb76c0f3c4166eaac` |
| `scripts/gen_recipes_index.py` | `6c2cfc95c041c66163f2841f39253ee458c07712b277277914a183a8e000b001` |
| `scripts/gen_search_golden.py` | `d482828e956c06208d94aad27f6843d722ea32be70ee6e998d4a4e487aa9f53d` |
| `scripts/gen_unicode61.py` | `914af4276d8fe871b14d85e459b5903429f6037fb3a9b42ccbf3ea1f34baaf0c` |
| `scripts/glean_cli_helper.py` | `8e99e967de692bebc7e1628a106709de9493e122fa9b5e67132144e52dc9b356` |
| `scripts/install.sh` | `755316f5ddbc2532b87007be1307ee53ef68827a1f81c7b1fdfb65d246f4a9e1` |
| `scripts/maintenance_safety.py` | `6f9a42484583866138dbf24c724bb515fae268db208b1452585d3e450130b161` |
| `scripts/make_chrome_icons.py` | `dbff46a5f337f3d259df4682571d66cb5e47fb7a8d3e0568f17e8241db10ed4b` |
| `scripts/offline_test.py` | `1f70cb9e3ad7c506b10f6f92bfcc8dbb24b95048c42c573c0336460b8245854f` |
| `scripts/package_chrome_extension.py` | `bcc02347313275e3880b1569273e6fccb6f0269196b5223527cc821423fd3466` |
| `scripts/redact_corpus.py` | `6036f2619bc2fff58a4b6951164c2211bfbc10a4594c4dc0e566e465ad729c7f` |
| `scripts/rotate_workflow_logs.py` | `629a81916203ce7c11e570f63814372c78c942be332ca1382236de493c5404ca` |
| `scripts/sweep_customers.py` | `632c42914061237504bbdb2e4cda08b147128523895616e04ee16141934c0e83` |
| `scripts/sync_corpus.sh` | `8a41726df3bda72b54dcd199a407529979c34766acd976d0e704d35cbaa9566d` |
| `scripts/sync_corpus_sources.py` | `1a91f2246132c90796adac19746694506d6a0c9ea43593628ec952b350ddab2b` |
| `scripts/test_isolation.py` | `1b1d64f48ada6d6e2c6081c9367482ea41c8e7ad7883817045c9c7c36c4cc859` |
| `scripts/watch_and_index.sh` | `691eacfba4816faa090cb7800d61fb57dda2fa888af45ab6a4f372a4390ef741` |
| `tests/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/conftest.py` | `cc8cc24412c75065ed349be804923deb67c95aa30ed545e79440befc71620e39` |
| `tests/test_cdo_hardening.py` | `db2c66af0ed3538dff7b7cb5d50c42af65662df5fe58cc85b5ff4d24ac8399fb` |
| `tests/test_chrome_autoupdate.py` | `ca7b3b63ba104e0e083d2277ed6405bcadccf3adb82b1e934ab5fb58786429b0` |
| `tests/test_core.py` | `b8b7a1daab054194924a0801c4de6ba9ecca86f787ca5598f5eed4a818edec70` |
| `tests/test_core_preservation.py` | `9d176d5698e3d6b8d1aa730a39e3269827f95389a759e5aafba40345e9e1f8e9` |
| `tests/test_corpus_autoupdate.py` | `fb9592af040b13908df1b0c79f47df6ba91becba7b9ed8ae14c681722300f499` |
| `tests/test_embed_backend.py` | `7b07e3aebe19480cdee73241c0b6032523f7b138622f0814100439b8cfca18a1` |
| `tests/test_generator_preservation.py` | `2cfe76bffaf5d2efaad03d21886986f6536bd429b071975e65cc723a8785cc9e` |
| `tests/test_iteration2_python.py` | `e608373823883551c62d5a880087a4adf68ff75dd88d3c5a36d136d529cbbbae` |
| `tests/test_iteration2_scripts.py` | `ca259e2e17209e3ee90645cfa61c2831a815829faa47e3ed7e23d4ef56fc69b3` |
| `tests/test_js_lint_parity.py` | `4bb05c5816f7c9de719ba919ceda67edfc938eb6dfaddabf41d40d39bd5291f5` |
| `tests/test_js_parity.py` | `ee125b806663e7b78a8c4af12125e27c5577c0ff61592013eb6af8973188b0cc` |
| `tests/test_lint_preservation.py` | `9d69d31317560afb7fe45be7c66631ff539285c345b84ca5039656dc36f6aae1` |
| `tests/test_lsp_e2e.py` | `18170449fe29f44d15a4a7be8f1dabe041d3da2020b2626b0b3d7b34509280f5` |
| `tests/test_maintenance.py` | `a00257a6c38df105364deaa69b11e15148c1028af92c8e096484e635afadca80` |
| `tests/test_mcp.py` | `d1b36bb210556efce8d6f4583ae020b0f2b7e5ebb7765ecc84a48b1911f69621` |
| `tests/test_mql.py` | `167d3cc0addadd6ef8ab26e277e93583bcc6a1f709fe56fc010b38bf91ac59e3` |
| `tests/test_normalize.py` | `ec878c321307b8bb7d0018893bb04ef47884695a844e1c517f30e854b3f8019c` |
| `tests/test_optimize.py` | `3531760b303fb7ada54307afb2bde59a17df0dce76bec6d575f912226ab9581c` |
| `tests/test_providers.py` | `88666b55b24d4127973c8ea285d10897260934252f7181a4fd33fe16f9ae7622` |
| `tests/test_recipes.py` | `21387d26fcf3dfa4aa5cb45e869b724017172f0e4970258b5500fce17cc5667f` |
| `tests/test_test_isolation.py` | `914f1e4ea1232154f7a039499486e13f690b3337387a415420a20fcb23184c11` |
| `tests/test_tooling_integrity.py` | `2cbc1b36b9ff626d98ad1166f8c284f429bb0a5587400ccb9ce904294d19ef3b` |
| `tests/test_tooling_regressions.py` | `b01a634dcec0cdd9e3097b03c75036df59139289f46b36e288bfb75469fd6654` |
| `tests/test_tui.py` | `24963290d2d04ba7d33ec8e042c3da6ea750d6b1251f960ba92985c16939ec47` |
| `tests/test_unicode61.py` | `aa8e0d3f0e9e589afc3e4964272d69bc428bbe77687de1bb7cb70c7382a5e39a` |
| `tests/test_web_search.py` | `dc9c7d863f8257715f1e71c7b371b6e2da9bf5266fca03aeb605e141fb7d941e` |

## Subsequent maintained source/test additions

At this proposal snapshot, 16 new source/test files from applied manifests and
normal upstream integration are
separately inventoried below. They received ordinary repair/regression work, not
the frozen gate-2 15-pass audit. These are observed current byte hashes, not final
remote-tree proof. The corpus-generation and public-install tests are included in this observed
inventory. The delivery owner reconciles any later additions before publication.

| Added maintained file | Observed current SHA256 | Coverage class |
|---|---|---|
| `editors/chrome/test/app-completion.mjs` | `9af99f27106813ac4e4ece079c308a0b27e6b1ff9e51739d624778b857c167ec` | ordinary repair/test; outside frozen 145 |
| `editors/chrome/test/counted-source.mjs` | `d08d61a1c97096d7f95c96cf33d0ea041452d7e0c81dcc19d1fb2422620ecd87` | ordinary repair/test; outside frozen 145 |
| `editors/chrome/test/extension-under-test.mjs` | `37c597c61ed80f3e678efa24d4ed0c20f96998a1e1d2d11cf8bb1db7db0fb876` | ordinary repair/test; outside frozen 145 |
| `editors/chrome/test/postgate-editors.test.mjs` | `e6c5ffc9a770f1b08d869542270780a19f48d19c1d3d683c8522d91968230775` | ordinary repair/test; outside frozen 145 |
| `editors/chrome/test/postgate-mql.test.mjs` | `41f439e77dfb75cacdbe2f21e81604ca3b775c36b947e243085576722f710798` | ordinary repair/test; outside frozen 145 |
| `editors/vscode/server-process.js` | `b606be560d4c4876afd436ece181abd1a2852fbc8656d848d57d7a2ed6f32dee` | ordinary repair/test; outside frozen 145 |
| `editors/vscode/test/lifecycle.test.js` | `851024c1df39803ac6cd57070b4d0bacfc5a50cadcb4020f63a3437ec72dfeb9` | ordinary repair/test; outside frozen 145 |
| `scripts/sync_corpus_transaction.py` | `fa4ab73fcefd29bf87125c840abb0faaf9a294bda92b6973f64bd6f37fd2c080` | ordinary repair/test; outside frozen 145 |
| `tests/test_ci_public_install.py` | `8b0dabd2ed91206e056d44816461d1a80890fd914ed64b681fcde52ab93f9106` | ordinary repair/test; outside frozen 145 |
| `tests/test_corpus_generation.py` | `095b21beab730e57f9643bf5178209f50b1e7ea941cf23a3b192c3f9cf3fcb49` | ordinary repair/test; outside frozen 145 |
| `tests/test_linux_offline_guard.py` | `db8b01ebf7ca914a73d3304d901f286f0c6c3354e4b02f6f41ac9782bb685b66` | ordinary repair/test; outside frozen 145 |
| `tests/test_postgate_core.py` | `a8fb497b44ffeb8c8869e26bc8ba107ade0b4fe09137d4467487fc1d58904da4` | ordinary repair/test; outside frozen 145 |
| `tests/test_postgate_mql.py` | `8b949dcf079b2e924c7352c0a7d9f2e01aecf4e94bec5faebda4775c8eeec820` | ordinary repair/test; outside frozen 145 |
| `tests/test_postgate_python.py` | `f1708b63cd55e487fd2f53ffb1d66660fdf32fd0eca369c1bd063a2dbd5583e6` | ordinary repair/test; outside frozen 145 |
| `tests/test_publication_preservation.py` | `e42ec82afeaef8afa7788658ccb750b4117db747db38736555ee5442ee6684ae` | ordinary repair/test; outside frozen 145 |

| `scripts/ci_private_dependency.py` | `1e3512a6b885cd3916dff6810f03ef42603ad6b322f46507606a3194b299db7b` | ordinary upstream 15-pass review; outside frozen blind 145 |

Two pre-existing generated operator catalogs also changed under source/generator
and parity checks. These assets are not new source files or independently
15-pass-reviewed targets, and are not ordinary expected-output fixtures.

| Additional existing generated asset | Observed current SHA256 |
|---|---|
| `editors/chrome/lib/operators-data.js` | `57a3ddafb667f9250e1d44a32ca4103461d0049e3dda8386813f305b9660606a` |
| `editors/chrome/lib/operators.json` | `fca10bcaf04c9eb5c64ac9710b4f365a2f5f15f44e3017928dce43bb5bdb817a` |

**FINAL_SOURCE_INVENTORY:** Current maintained runtime/config/test scope is159 files:143 legacy diagnostic sources plus16 ordinary post-gate/upstream additions. The two legacy auxiliary targets (LICENSE prose and archive .gitkeep) remain separate from runtime counts. Generated operator catalog assets are consumer-verified separately. [Current source hash inventory](source-inventory-2026-11-12.json) records every current maintained path/hash and the difference between frozen gate evidence and ordinary post-gate review.

The inventory distinguishes current source hashes from immutable earlier review snapshots.
Do not include this report's own byte hash in its source table or silently expand
the 145-target frozen denominator. Final per-file convergence belongs in the
[optimizer ledger](code-deep-optimizer-2026-11-12.md); local CLEAN labels remain
separate from global blind dissent.

## Retained evidence and final validation

| Artifact | SHA256 / identity |
|---|---|
| blind-2-final-proof.json | `3e7bee89c2c4d6cc9668d02f779f6ea9209f977c793259b847bd0f5ad8431d30` |
| Frozen gate-2 inventory | `8bcf3f21109d0cccfd1ce664254812596acc421171f0a2c914ada83245bc11ae` |
| Frozen gate-2 collection | `9ceb8d7d5bbbf1e461e75824fe5a2e6430a5ea7f95f575c52b5d08e2f607b930` |
| Original postgate-before-manifest.json, 146 records | `4979a7a9443d6ccdf46f8d2f2c3f5c7ff17e41976f05da6f0c91022b10d33ffe` |

Core, MQL, Python, editor, publication, Linux and corpus-generation application
manifests retain exact before/after hashes, modes and path scope. Disposition
ledgers preserve individual corroboration, duplicates and limitations. Complete
raw logs/partial events stay external; no private log body was read for this
report. Final source coverage is not empirical model-quality evaluation. The source-head
08708f0 local result was 668 Python passes/2 skips plus the retained static,
package and Node evidence in final-local-checks.json; final-head CI and remote
content proof remain separate fields.

**FINAL_VALIDATION:** Actual integrated source at08708f0:668 Python tests passed,2 skipped (real ONNX unavailable and Linux-only proof on macOS); Chrome280 and VS Code20 passed. Ruff, compilation, shell syntax, five generator freshness checks, wheel, code-only Chrome ZIP and VSIX builds passed. Exact commands/results and later CI-repair checks are retained in the external delivery receipt. The independent production scope proof passed64 synthetic outputs and exact selected source/AST checks.

**FINAL_CI:** [PR7 checks](https://github.com/mithudso/mdb-expertise-search/pull/7/checks) cover macOS and Ubuntu on Python3.11/3.12/3.13. First integrated run43312948550 exposed Linux inherited-guard self-recognition and nested-runner failures; its failed result is retained. Final pushed-head CI must pass before merge; actual run IDs/results are recorded in the delivery receipt.

**FINAL_MERGE:** [PR7](https://github.com/mithudso/mdb-expertise-search/pull/7) records the final pushed and merged commit identities. This source audit does not infer delivery from an open PR or branch ancestry.

**FINAL_REMOTE:** Delivery verification compares the intended complete Git tree and every tracked blob/mode with the fetched remote default branch after merge. Exact tree/commit IDs and postmerge CI belong to the external delivery receipt.

The delivery owner supplies actual final-head checks and required CI, normal
upstream integration, remote default-tree proof and safe checkout/hub disposition.
A source census or passing local suite alone does not establish delivery.


### Required CI repair appendix

Run43312948550 exposed Linux inherited-isolation self-recognition failures.
Diagnostic run43314617512 proved only routeheader_ok failed: the successful IPv4
route read was exactly empty; all identity, capability, NoNewPrivs, down-loopback
and inert IPv6 predicates passed. Linux fib_route_seq_start returns NULL before
the header token when the main table is absent ([primary kernel source](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/%2B/627b7865c062ff642c0000f3a4775f1a44b986a4/net/ipv4/fib_trie.c)).
The correction accepts exactly empty or valid-header/zero-row IPv4 output.
Missing, unreadable, whitespace, malformed and nonempty controls remain rejected.
The synthetic empty-file regression was RED before and GREEN after the correction.
Actual socket assertions run in the fresh Python parent→Node→Python descendant
chain under the inherited kernel guard, with scratch state and fake factories.
The generic pytest socket mock is explicitly rejected as kernel evidence.
After this correction the actual macOS full suite passed673 tests with2 skips;
Ruff passed. Final full-matrix CI remains a required delivery gate at PR7.
These are necessary ordinary CI repairs, with no third blind gate or budget reset.
