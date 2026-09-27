# Retrieval accuracy benchmark

Run at: 2026-09-27T03:30:11.196726+00:00
Git HEAD at run: `cb070a41c7114bd22bffc35e307a7a620831e36a` (worktree changes may have been present).
Models: `nomic-embed-text` embeddings; `llama3.2:3b` configured for answers (not used in retrieval scoring).
Corpus: 1070 PDF pages, 5007 indexed chunks, 5 files.
Queries: 28 excerpt-verified questions.

## Results

| Method | Source hit@3 | Source hit@5 | Source MRR | Page hit@3 | Page hit@5 | Page MRR |
|---|---:|---:|---:|---:|---:|---:|
| vector_only | 92.9% | 100.0% | 0.893 | 67.9% | 75.0% | 0.635 |
| substring_keyword | 78.6% | 89.3% | 0.747 | 67.9% | 78.6% | 0.622 |
| bm25_keyword | 100.0% | 100.0% | 1.000 | 89.3% | 92.9% | 0.864 |
| hybrid_substring | 89.3% | 89.3% | 0.845 | 75.0% | 75.0% | 0.702 |
| hybrid_bm25 | 100.0% | 100.0% | 1.000 | 89.3% | 89.3% | 0.857 |
| hybrid_bm25_50 | 100.0% | 100.0% | 1.000 | 89.3% | 89.3% | 0.810 |
| hybrid_bm25_75 | 100.0% | 100.0% | 0.982 | 89.3% | 89.3% | 0.798 |

Hit@k and reciprocal rank inspect the top k *chunks*. Source metrics match their file name; page metrics match file name and physical PDF page. MRR is the mean reciprocal rank of the first match. Each method returns at most five chunks. Hybrid candidate pools contain ten vector and ten keyword chunks. `hybrid_bm25` is the production 0.25 vector / 0.75 BM25 blend; the `_50` and `_75` variants use 0.50 and 0.75 vector weights. `hybrid_substring` retains the old 0.50/0.50 comparison.

## Query changes

All 50 old queries were removed because their labels all pointed to `zoning.pdf` regardless of answer location. The first 20 replacement questions and eight additional questions below were written from cited PDF passages. None of the old labels was carried forward. The additional questions were also used during development, so this is not a blind test set.

### Removed queries

| Old # | Removed query |
|---:|---|
| 1 | zoning regulations |
| 2 | commercial lease terms |
| 3 | property maintenance responsibility |
| 4 | late rent penalty |
| 5 | sublease permission |
| 6 | tenant deposit requirements |
| 7 | landlord insurance obligations |
| 8 | lease renewal process |
| 9 | eviction procedures |
| 10 | damage liability clause |
| 11 | utility payment responsibility |
| 12 | noise complaint resolution |
| 13 | pet policy restrictions |
| 14 | parking space allocation |
| 15 | renovation approval |
| 16 | termination notice period |
| 17 | security deposit return |
| 18 | property inspection rights |
| 19 | rent increase limits |
| 20 | breach of contract remedies |
| 21 | common area maintenance |
| 22 | HOA fees and charges |
| 23 | property tax assessment |
| 24 | mortgage payment schedule |
| 25 | boundary line disputes |
| 26 | easement agreements |
| 27 | lien enforcement procedures |
| 28 | title insurance coverage |
| 29 | escrow account management |
| 30 | closing cost breakdown |
| 31 | appraisal contingency |
| 32 | home inspection requirements |
| 33 | lead paint disclosure |
| 34 | radon testing procedures |
| 35 | flood zone certification |
| 36 | code violation remediation |
| 37 | accessibility compliance |
| 38 | fire safety standards |
| 39 | environmental hazards |
| 40 | asbestos disclosure |
| 41 | mold remediation requirements |
| 42 | foundation repair warranty |
| 43 | roof repair obligations |
| 44 | plumbing maintenance responsibility |
| 45 | electrical system safety |
| 46 | HVAC maintenance schedule |
| 47 | appliance warranty terms |
| 48 | pest control procedures |
| 49 | lawn and landscape maintenance |
| 50 | snow removal liability |

### Added queries and label evidence

Each label was set by reading the specified physical PDF page; the benchmark checks that its evidence excerpt occurs on that page before scoring.

| ID | Query | Source | PDF page(s) | Evidence excerpt |
|---|---|---|---:|---|
| iss_01 | What residential density does Issaquah's Village Residential district aim to preserve? | zoning.pdf | 2 | moderate density residential uses and compatible commercial uses |
| iss_02 | How close to mineral resource land triggers a development permit notice in Issaquah? | zoning.pdf | 3 | within five hundred (500) feet of, lands designated as mineral resource lands |
| iss_03 | What minimum number of floors is required for Issaquah Vertical Mixed Use parcels with required ground floor frontages? | zoning.pdf | 4 | buildings are required to be a minimum of two floors |
| iss_04 | In Issaquah, commercial boarding kennels may be accessory to which businesses? | zoning.pdf | 10 | Commercial Boarding Kennels are permitted only as an accessory use to a Veterinary Clinic or Pet Store |
| sum_01 | In the generalized zoning summary, what minimum lot area is listed for the A1 Agricultural zone? | E Generalized Summary of Zoning Regulations.pdf | 2 | 5 acres 2.5 acres 300 ft. |
| sum_02 | How many parking spaces does the generalized zoning summary list for R2 two-family dwellings? | E Generalized Summary of Zoning Regulations.pdf | 3 | 2 spaces, one covered |
| sum_03 | What maximum height does the generalized zoning summary list for CR Limited Commercial? | E Generalized Summary of Zoning Regulations.pdf | 4 | 6 (8) 75 ft. (8) 10 ft. min. |
| sum_04 | What does the D Development Limitation designation restrict in the generalized zoning summary? | E Generalized Summary of Zoning Regulations.pdf | 7 | D Development Limitation Restricts heights, floor area ratio, percent of lot coverage, building setbacks |
| urb_01 | What is the maximum shed area under Urbana's accessory structure rules? | article_v_-_use_regulations.pdf | 2 | maximum area for a shed shall be 120 square feet |
| urb_02 | How far from a principal use may accessory off-street parking be placed on a separate zoning lot in Urbana? | article_v_-_use_regulations.pdf | 3 | within 600 feet (exclusive of rights-of-way) of the principal use |
| urb_03 | How many people may occupy a boarding or rooming house in Urbana? | article_v_-_use_regulations.pdf | 6 | no more than 15 persons, related or unrelated |
| urb_04 | Within what distance of a residentially zoned lot does an Urbana cannabis cultivation center need a special use permit? | article_v_-_use_regulations.pdf | 9 | within 300 feet of any residentially zoned lot |
| uni_01 | What is the maximum floor area for a freestanding guest house in Union City? | zoning-ordinance-082024-rev.pdf | 38 | A freestanding guest house shall not exceed 700 square feet |
| uni_02 | What maximum front-yard wall or fence height applies in Union City? | zoning-ordinance-082024-rev.pdf | 40 | No wall or fence shall exceed four (4) feet in height within or along a boundary of a front yard |
| uni_03 | What percentage of a Union City commercial building's street-facing exterior siding must be brick or stone? | zoning-ordinance-082024-rev.pdf | 45 | a minimum of 80% of the exterior siding materials |
| uni_04 | How many donation boxes may be placed on a Union City zoning lot? | zoning-ordinance-082024-rev.pdf | 46 | No more than one donation box shall be permitted on each zoning lot |
| cha_01 | Under Charleston section 54-211, in which zoning districts may a home occupation be established? | Charleston, SC Zoning.pdf | 200 | A home occupation may be established on a property in any zon ing district |
| cha_02 | What maximum building height does Charleston Height District 8 permit? | Charleston, SC Zoning.pdf | 400 | Maximum building height shall not exceed 8 stories |
| cha_03 | How many sandwich board signs may a single Charleston building have on private property? | Charleston, SC Zoning.pdf | 500 | Only one sandwich board sign shall be allowed for any sing le building |
| cha_04 | How many watercraft slips define a Charleston community dock? | Charleston, SC Zoning.pdf | 620 | greater than or equal to 5 watercraft slips and less than or equal to 10 watercraft slips |
| held_iss_01 | In Issaquah's land use table, what does P2 tell an applicant about review? | zoning.pdf | 5 | P(Number) = PERMITTED with Level of Review (0, 1, 2, 3) |
| held_sum_01 | How much front yard does a surface parking zone need when it is combined with an agricultural or residential zone in the generalized summary? | E Generalized Summary of Zoning Regulations.pdf | 6 | 10 ft. in combination with an A or R Zone; otherwise none |
| held_urb_01 | In Urbana, how far must a proposed gaming hall be from another licensed gaming hall? | article_v_-_use_regulations.pdf | 16 | a minimum of five hundred feet from any other licensed gaming hall |
| held_uni_01 | What minimum lot size does Union City require for a cemetery? | zoning-ordinance-082024-rev.pdf | 51 | Minimum lot area shall be ten (10) acres |
| held_uni_02 | Does Union City's R-2 district list noncommercial agriculture among its permitted uses? | zoning-ordinance-082024-rev.pdf | 53 | Non-commercial agriculture |
| held_cha_01 | What is the minimum height for a principal structure in Charleston's 55/30 height district? | Charleston, SC Zoning.pdf | 406, 405 | nor shall the principal structure be lower than thirty (30) feet |
| held_cha_02 | For a Charleston development with at least twenty business units, what is the per-face area limit for its monument sign? | Charleston, SC Zoning.pdf | 505 | No sign shall exceed one hundred (100) square feet per fac e |
| held_cha_03 | In Charleston, where does someone appeal an administrative decision about a sidewalk cafe permit? | Charleston, SC Zoning.pdf | 205 | Board of Zoning Appeals Site Design |
