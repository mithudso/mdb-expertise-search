# Maintained-source coverage — 2026-11-12

The complete maintained runtime, tools, tests, configuration and editor surface is
145 files at repair checkpoint `a96aee5409964dbf45cdef0b18b6708970a53280`.
The initial112-file diagnostic collection is complete (109 external plus3 native).
Gate1 covers129 unique checkpoint files, with130 substantive reports because one
generator changed hashes. The128 unchanged hashes and current generator report
were independently reconciled. Gate2 reviews all145 current files, including16
additional maintained files; its result is pending in this in-progress ledger.

Each file receives the injection gate and15 per-file verdicts: C1–C3, S1–S5,
P1–P2, M1, intra-file M2, M4, T1 and T4 (test-only; N/A elsewhere).
Repo M3, T2, T3, cross-file M2 and test-performance decisions are recorded separately
in the optimizer report. Coverage is evidence accounting, not a CLEAN claim.

The514 excluded records comprise444 protected data identities and70 generated,
fixture, lockfile or binary data records. Protected paths use opaque identities in
the external receipt. Their byte hashes match the original inventory. This is a
metadata preservation census; protected corpus bodies were not code-audited.
Synthetic expected outputs are checked by consumers; four ordinary MQL optimizer
expectations changed under narrow authorization. Search/chunk/vector fixtures and
all lint expectations retain their original bytes. Generated Unicode61 lookup
modules are included in maintained-source review; their generator is reviewed too.
Markdown and license prose are handled by the bootstrap/documentation route.
No vendored node_modules, virtualenv, build output or model/cache/store enters scope.
No50-file limit was applied.

The external evidence retains original and sanitized hashes, exact report targets,
all pass rows, completed turns, raw partials, process admission receipts and per-file
convergence outputs. Existing complete evidence was reused; no round was reset.

| Maintained file | Frozen source SHA256 |
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
| `mdbx/safety.py` | `979da24bfab67fb2d1d94fd2a0641e90188ff464dee032665d47adce15d6983c` |
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
| `tests/test_iteration2_scripts.py` | `6e8d32d08d70fc043e4716ac92fac83bc4c97c58c627303a92b8b34fdfaf51ea` |
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
