# Facts the product may state

The UI, report, README and pitch may state only these facts, in these words or narrower. Checked 7 Nov 2026.

| Topic | Verified statement | Source |
| --- | --- | --- |
| Pseudonymisation | GDPR Article 4(5) defines it as processing so data can no longer be attributed to a person without additional information kept separately. Pseudonymised data is still personal data (Recital 26). | GDPR; EDPB Guidelines 01/2025, https://www.edpb.europa.eu/our-work-tools/our-documents/publication-type/guidelines_en |
| EDPB guidance | The EDPB adopted Guidelines 01/2025 on pseudonymisation on 16 January 2025; public consultation closed 28 February 2025. | https://www.hunton.com/insights/publications/edpb-advises-on-pseudonymisation-for-gdpr-compliance |
| Keyed pseudonym | HMAC-SHA256 with a secret key held only by the controller; without the key, a pseudonym cannot be recomputed from a guessed identifier. | Standard HMAC property; proving ground PET_PLAYBOOK.md |
| Why not a plain hash | A HETU has a small, enumerable space; a public generator lists over 276 million valid codes, so an unkeyed hash can be reversed by trying them all. pets-eval runs this attack. | https://gist.github.com/ollipal/d27c33e011e45a6773870fea29279d91 |
| HETU format | DDMMYY + century sign + individual number + check character. The check character is the 9-digit number mod 31 mapped to 0123456789ABCDEFHJKLMNPRSTUVWXY. | https://arthurdejong.org/python-stdnum/doc/stdnum.fi.hetu ; Finlex 690/2022 |
| HETU century signs | + for the 1800s; -, Y, X, W, V, U for the 1900s; A to F for the 2000s. New signs in force from 1 January 2023; first new-sign code issued in December 2023. | https://valtioneuvosto.fi/en/-/10623/availability-of-sufficient-personal-identity-codes-to-be-ensured-using-new-intermediate-characters ; https://stat.fi/meta/kas/hetu.html |
| k-anonymity | Every combination of quasi-identifier values in the release is shared by at least k rows. It limits singling out on the stated quasi-identifiers only; it does not stop attribute inference inside a uniform group. | Sweeney 2002; https://pypi.org/project/pycanon/ |
| l-diversity | Each group must contain at least l well-represented values of the sensitive attribute; it addresses the homogeneity gap in k-anonymity. | Machanavajjhala et al., ICDE 2006 |
| Workload-aware anonymisation | Quality should be judged against the tasks the data will serve. | LeFevre et al., KDD 2006 |
| Differential privacy | A mechanism is epsilon-DP if adding or removing one person changes any output's probability by at most a factor e^epsilon. Needs a stated unit, contribution bound and budget. | Dwork et al. 2006; https://github.com/opendp/opendp |
| Text anonymisation | Removing predefined entity types is not enough; evaluation should weight recall and consider indirect identifiers. | TAB, Pilán et al. 2022, https://aclanthology.org/2022.cl-4.19 |
| LLM inference risk | LLMs infer personal attributes from text near human level; adversarial LLM feedback improves anonymisation. | Staab et al., ICLR 2025 |
| Proving-ground baselines | B2 regex redaction leaks 71 to 88 % of identifying values in free text; B2-k utility falls to 0.00 on HEALTH-S2 and CITY-S3. | vendor/proving_ground/results/, pets-eval 1.0.0 |
| EDPB pseudonymisation terms | EDPB Guidelines 01/2025 describe pseudonymisation with a pseudonymisation secret, a pseudonymisation domain and additional information kept separately. | EDPB Guidelines 01/2025 |
| LLM step | The LLM step is optional and swappable; every release is also produced and verified with it switched off. | `api/pipeline/llm.py`; `--no-llm` runs in every phase report |

Words the product never uses: anonymous, anonymised, GDPR compliant, secure, guaranteed (except "epsilon-DP guarantee" when a DP mechanism with accounting actually ran).
