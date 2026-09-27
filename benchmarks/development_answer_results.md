# Development answer evaluation

Run at: 2026-09-27T01:42:54.012609+00:00
Git HEAD at run: `3f2fd87b8c608c3a90bcec28a7a4b045685b1e90` (worktree changes may have been present).
Dataset: `development_queries.json`.
Models: `llama3.2:3b` and `nomic-embed-text`.
Queries: 12 (8 answerable, 3 unanswerable, 1 ambiguous).

Automated checks passed: 9/12.

Answerable items pass when the answer contains an accepted phrase and cites the labeled physical PDF page. Unanswerable items require the exact abstention. The ambiguous item requires a clarification question. These are screening checks, not proof that every sentence is factually supported. The no-answer and ambiguity labels are task expectations, not exhaustive corpus proofs.

## Per-query results

| ID | Kind | Fact/behavior | Labeled page citation | Valid refs | Pass |
|---|---|---:|---:|---:|---:|
| held_iss_01 | answerable | True | True | True | True |
| held_sum_01 | answerable | False | False | True | False |
| held_urb_01 | answerable | True | True | True | True |
| held_uni_01 | answerable | True | False | True | False |
| held_uni_02 | answerable | True | True | True | True |
| held_cha_01 | answerable | True | True | True | True |
| held_cha_02 | answerable | True | True | True | True |
| held_cha_03 | answerable | False | False | True | False |
| held_absent_01 | unanswerable | True | True | True | True |
| held_absent_02 | unanswerable | True | True | True | True |
| held_absent_03 | unanswerable | True | True | True | True |
| held_ambiguous_01 | ambiguous | True | True | True | True |

## Answers for review

### held_iss_01

Question: In Issaquah's land use table, what does P2 tell an applicant about review?

Answer: Jurisdiction: Issaquah | District: not specified | Document version: Updated 2-5-20 | Source: zoning.pdf
P2 = Permitted with Level 2 Review [1].

Sources: [{"source": "zoning.pdf", "page": 5, "excerpt": "B. Table 4.3B Table of Permitted Land Uses \n1. Permitted Uses:  P = PERMITTED; P(Number) = PERMITTED with Level of Review \n(0, 1, 2, 3) [i.e. P2 = Permitted with Level 2 Review]; Empty box = NOT PERMITTED. \n2. Unclassified Uses. Those uses which are not listed on the table below but are listed in IMC \n18.06.130, Table of Permitted Land Uses, are Not Permitted in any Central Issaquah zone.  \nThose remaining uses which are not listed on the table below and are also not listed in IMC \n18.06.130, Ta"}, {"source": "zoning.pdf", "page": 11, "excerpt": "Issaquah Zoning Map and 4B Vertical Mixed Use Overlay. \n24. Refer to 4.4.F Standards for Vertical Mixed Use Overlay for Ground Floor Use requirements.  \n25. Parcels fronting East Lake Sammamish Parkway SE or 221st Place SE only \n \n4.4 District Standards \nA. Applicability. This subsection sets forth the dimensional requirements for each zoning district \nin Central Issaquah. The District Standards Table found in IMC 18.07.360 does not apply in the \nCentral Issaquah zoning districts. Each structure"}, {"source": "zoning-ordinance-082024-rev.pdf", "page": 242, "excerpt": "August 20, 2024, Rev. Page 233 \n \niii. In what way are the extraordinary and exceptional conditions, identified above, \npeculiar to the use or development proposed or to the particular piece of \nproperty involved? \n \niv. What conditions, factors and/or circumstances give assurance that if the \nrequested variance were granted that such variance would not cause substantial \ndetriment to other property owners or tenants, or to the public good and would \nnot impair the purpose and intent of the ordi"}]

### held_sum_01

Question: How much front yard does a surface parking zone need when it is combined with an agricultural or residential zone in the generalized summary?

Answer: I don't know based on these documents.

Sources: [{"source": "E Generalized Summary of Zoning Regulations.pdf", "page": 6, "excerpt": "Zone Use\nMaximum Height Required yards Minimum \nArea Per \nl ot/ Unit\nMin. \nl ot \nWidthstories feet front side Rear\nPARking\nP\nAutomobile Parking–Surface and \nUnderground  \nSurface Parking;  \nLand in a P Zone may also be \nClassified in A or R Zone\nunlimited (8)\n10 ft. in combination \nwith an A or R Zone; \notherwise none\nnone none, unless also in \nan A or R Zone\nPB\nParking Building  \nP Zone Uses,  \nAutomobile Parking Within aBuilding\n0 ft., 5 ft., or 10 ft., \ndepending on zoning \nfrontage and zonin"}]

### held_urb_01

Question: In Urbana, how far must a proposed gaming hall be from another licensed gaming hall?

Answer: Jurisdiction: Urbana | District: not specified | Document version: not identified | Source: article_v_-_use_regulations.pdf
In Urbana, a proposed gaming hall must be at least 500 feet from another licensed gaming hall. [1]

Sources: [{"source": "article_v_-_use_regulations.pdf", "page": 16, "excerpt": "****See Table VII-1 for Standards for Specific Conditional Uses \n***** The establishment requesting a license for a principal use gaming hall shall be a minimum of five hundred feet from any other licensed \ngaming hall or pre-existing Day Care Facility, Day Care Home, School, or Place of Worship, as defined under the Religious Corporation Act \n(805 ILCS 110/0.01 et seq.). The establishment requesting a license for a principal use gaming hall shall also be a minimum of two \nhundred and fifty feet"}]

### held_uni_01

Question: What minimum lot size does Union City require for a cemetery?

Answer: Jurisdiction: Union City, Georgia | District: R-4 | Document version: August 20, 2024, Rev. | Source: zoning-ordinance-082024-rev.pdf
According to the context, Union City requires a minimum lot area of ten (10) acres for a cemetery [1].

Sources: [{"source": "zoning-ordinance-082024-rev.pdf", "page": 63, "excerpt": "planted buffer strip. \n \n8. Cemetery, provided: \n \na. Minimum lot area shall be ten (10) acres; \n \nb. Gravesites shall be set back at least 50 feet from all property lines; \n \nc. No structure other than grave markers shall be located within 35 feetof property \nzoned for residential use;"}, {"source": "zoning-ordinance-082024-rev.pdf", "page": 76, "excerpt": "3. Schools and their customary related uses, provided: \n \na. Minimum lot size is three (3) acres; \n \nb. Minimum lot frontage is at least 200 feet; \n \nc. All buildings are located on a lot fronting a major or collector street, as \ndetermined by the Planning Commission; and \n \nd. All buildings are placed not less than 50 feet from any property line and are \nseparated from any such property line, excluding the front property line, by a \nplanted buffer strip. \n \n4. Cemetery, provided: \n \na. Minimum "}, {"source": "zoning-ordinance-082024-rev.pdf", "page": 16, "excerpt": "August 20, 2024, Rev. Page 7 \n \nand including four-inch caliper size, and twelve (12) inches above the ground for larger \nsizes. \n \n3-39 Car Wash. An establishment used for washing and cleaning of passenger vehicles, \nrecreational vehicles, and other light duty equipment, including facilities containing \nmechanical devices for washing and those that are self-service/coin operated. (Ordinance \n2022-03; 12/08/22) \n \n3-40 Cemetery. A burial ground. \n \n3-41 Cemetery, Commercial. The operation of a b"}]

### held_uni_02

Question: Does Union City's R-2 district list noncommercial agriculture among its permitted uses?

Answer: Jurisdiction: Union City, Georgia | District: R-2 | Document version: August 20, 2024, Rev. | Source: zoning-ordinance-082024-rev.pdf
Yes, non-commercial agriculture is listed as a permitted use in Union City's R-2 district. [1]

Sources: [{"source": "zoning-ordinance-082024-rev.pdf", "page": 53, "excerpt": "August 20, 2024, Rev. Page 44 \n \n6-2 R-2 Single-Family Residential. \n \nA. Description of District. The R-2 single-family residential district is intended to provide \nsuitable open areas for single-family, detached dwellings at low to moderate densities, \nwith access to public water and sewerage. \n \nB. Permitted Uses. Within the R-2 Zoning District, the following Permitted uses shall be \nallowed: \n \n1. Single-family detached dwellings; \n \n2. Accessory buildings and uses; \n \n3. Clubs and recreatio"}]

### held_cha_01

Question: What is the minimum height for a principal structure in Charleston's 55/30 height district?

Answer: Jurisdiction: Charleston, South Carolina | District: not specified | Document version: Supplement No. 25, November 2025 | Source: Charleston, SC Zoning.pdf
In Charleston's 55/30 height district, the minimum height for a principal structure is thirty (30) feet [1].

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 405, "excerpt": "(Ord. No. 2017-085, § 1, 8-15-17; Ord. No. 2020-014, § 1, 1-28 -20) \nSec. 54-306.V.  Height District 55/30 S. \nIn this district: \n1. No part of a structure shall exceed the height of fifty-fiv e (55) feet, nor shall the \nprincipal structure be lower than thirty (30) feet. \n§ 54-306.T  § 54-306.VSITE REGULATIONS\n3-20.5Supp. No. 19"}, {"source": "Charleston, SC Zoning.pdf", "page": 406, "excerpt": "2. All structures shall have no minimum set back from street ri ght-of-way lines, subject \nto provisions of Article 3: Part 10. \n(Ord. No. 2017-085, § 1, 8-15-17; Ord. No. 2020-014, § 1, 1-28 -20) \nSec. 54-306.W.  Height District 55/30. \nIn this district: \n1. No part of a structure shall exceed the height of fifty-fiv e (55) feet, nor shall the \nprincipal structure be lower than thirty (30) feet. \n2. All structures shall have no set back from street right-of- way lines, subject to \nprovisions of"}, {"source": "Charleston, SC Zoning.pdf", "page": 402, "excerpt": "Sec. 54-306.O.  Height District 100/30. \nIn this district: \n1. The minimum height for a structure fronting on a street is t hirty (30) feet, and the \nminimum height on the ground floor of a structure fifteen (15 ) feet. \n2. The maximum height of a structure along north-south orien ted streets is four (4) \nstories. The height along north-south oriented streets sha ll be maintained from the \nedge of the right-of-way into the interior of the lot for a dist ance of one hundred (100) \nfeet, except as"}]

### held_cha_02

Question: For a Charleston development with at least twenty business units, what is the per-face area limit for its monument sign?

Answer: Jurisdiction: Charleston, South Carolina | District: not specified | Document version: Supplement No. 25, November 2025 | Source: Charleston, SC Zoning.pdf
For a Charleston development with at least twenty business units, no sign shall exceed one hundred (100) square feet per face [2].

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 504, "excerpt": "2. For a development containing more than three (3) business units and fewer\nthan twenty (20) business units, one (1) monument sign shall be permitted as\nfollows:\n(a) No sign shall exceed sixty (60) square feet per face or one hundred and\ntwenty (120) square feet of total sign face area. No sign shal l exceed\nfourteen (14) feet in height.\n(b) Monument signs may be illuminated internally or with a shi elded spot\nlight located at the base of the sign. Plastic face signs shal l have opaque\nbackgrou"}, {"source": "Charleston, SC Zoning.pdf", "page": 505, "excerpt": "3. For a development containing twenty (20) or more business units, or 150,000\nsquare feet or more of floor area, one (1) monument sign shall be permitted as\nfollows:\n(a) No sign shall exceed one hundred (100) square feet per fac e or two\nhundred (200) square feet of total sign face area. No sign sha ll exceed\nfourteen (14) feet in height.\n(b) Monument signs may be illuminated internally or with a shi elded spot\nlight located at the base of the sign. Plastic face signs shal l have opaque\nbackgro"}, {"source": "Charleston, SC Zoning.pdf", "page": 503, "excerpt": "property owner of the parcel on which the sign is to be located stating\nthat the property owner will allow the sign to be erected at th e location\nindicated on the site plan.\n(Ord. No. 2018-031, § 8, 4-10-18)\nSec. 54-415. Regulations for signs within all other distric ts.\nIn all other districts, only the following signs shall be per mitted:\na. Freestanding signs shall be permitted as follows:\n1. For a development containing three (3) or fewer business u nits, one (1)\nmonument sign shall be permi"}]

### held_cha_03

Question: In Charleston, where does someone appeal an administrative decision about a sidewalk cafe permit?

Answer: I don't know based on these documents.

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 681, "excerpt": "Meeting agendas are limited to no more than twenty-five (25) new applications and appeals. \nEach application or appeal shall require a fee as set by City C ouncil. \nSection 2.  Time Limit for Appeal of an Administrative Decis ion. \nAn appeal from an administrative decision must be filed with in ten (10) business days after \nactual notice of the decision by delivery of the approved app eal form and fee to the Zoning \nDivision office. \nSection 3.  Time Limit and Procedure for Appeal for Reconsid e"}, {"source": "Charleston, SC Zoning.pdf", "page": 721, "excerpt": "provided by the Rules of Procedure. \n   Article III.\nAppeals Procedure \nSection 1.  Form of Appeal—Administrative Decision. \nAppeals to the Board from an administrative decision may be ta ken by any person aggrieved \nby a determination of the administrative officer. Appeals s hall be filed on forms approved by \nthe Board and provided by the Secretary of the Board. Appeal f orms shall be made available \nin the City of Charleston Department of Planning and Preserv ation, 75 Calhoun Street, \nCharle"}, {"source": "Charleston, SC Zoning.pdf", "page": 688, "excerpt": "Section 2.  Time for Appeal for an Administrative Decision. \nAn appeal from an administrative decision must be filed with in fifteen (15) calendar days \nfrom the making of such decision, order, requirement or dete rmination. \nSection 3.  Calendar. \nAppeals shall be marked with the date of receipt and placed on the hearing calendar. \nSection 4.  Withdrawal of Appeal. \nAny appeal may be withdrawn by written notice delivered to the s ecretary prior to action by \nthe Board. An appeal may not be re-f"}]

### held_absent_01

Question: What is the battery capacity of the 2025 Tesla Model 3?

Answer: I don't know based on these documents.

Sources: [{"source": "zoning-ordinance-082024-rev.pdf", "page": 242, "excerpt": "August 20, 2024, Rev. Page 233 \n \niii. In what way are the extraordinary and exceptional conditions, identified above, \npeculiar to the use or development proposed or to the particular piece of \nproperty involved? \n \niv. What conditions, factors and/or circumstances give assurance that if the \nrequested variance were granted that such variance would not cause substantial \ndetriment to other property owners or tenants, or to the public good and would \nnot impair the purpose and intent of the ordi"}, {"source": "Charleston, SC Zoning.pdf", "page": 355, "excerpt": "system meets the capacity required and is functioning prope rly before a\ncertificate of occupancy is given.(c) Certificate of occup ancy . If the\ncommitted points in this category are not achieved, the owne r shall be\nrequired to substitute incentive options and earn all point s necessary to\njustify bonuses before a certificate of occupancy will be is sued. (d)\nLongevity . This incentive option shall exist and be maintai ned to its full\ncapacity by the owner for the life of the corresponding bui"}, {"source": "Charleston, SC Zoning.pdf", "page": 415, "excerpt": "USE NUMBER OF SPACES REQUIRED\n- Day care centers 2 per employee\n- Church, synagogue, place of worship (other\nthan on the peninsula)\n1 per 4 seats design capacity of the principal\nplace of worship; 80 percent of the required\nspaces may be provided at an off-site\npublic or private parking lot which is\naccessory to another use not open or operat-\ning during the time of weekend services\nand within 400 feet of the place of wor-\nship. Written permission from owner of lot\nindicating times parking is to"}]

### held_absent_02

Question: Who won the 2024 Nobel Prize in Physics?

Answer: I don't know based on these documents.

Sources: [{"source": "zoning-ordinance-082024-rev.pdf", "page": 173, "excerpt": "August 20, 2024, Rev. Page 164 \n \nb. Roads, parking lots and impervious surfaces, except as specifically authorized in the \nprevious sections; \n \nc. Agricultural and forestry activities not conducted according to accepted Best \nManagement Practices; and \n \nd. Other activities as determined by the Applicant and recorded onthe legal instrument \nproviding for permanent protection. \n \n9. Ownership and Management of Open Space. \n \na. Ownership of Open Space. The applicant must identify the ownerof th"}, {"source": "Charleston, SC Zoning.pdf", "page": 607, "excerpt": "property damage and compromise public safety. Notwithstan ding ongoing efforts by the City \nto study and model the drainage conditions in the Basin and to update and implement \nregulations to alleviate flooding conditions there, it is e vident that, absent a thorough \nevaluation of the drainage patterns in portions of the Basin , of the development and \ninfrastructure in place, and of development that will reaso nably occur in these areas in the \nimmediate future, development in the Basin, both "}, {"source": "Charleston, SC Zoning.pdf", "page": 286, "excerpt": "approval requirements of the Design Review District and the requirements of part \n11 of this ordinance. \n(Ord. No. 2011-45, § 1, 6-21-11; Ord. No. 2012-386, §§ 1, 2, 10 -23-12; Ord. No. 2024-185, § 1, \n12-3-24) \nSec. 54-269.  Design Review Board created; composition, ap pointment and terms of \nmembers. \na. A Design Review Board is hereby established. Such board sh all consist of seven (7) \nboard members and two (2) alternates who do not hold any other public office or \nposition in the City of Ch"}]

### held_absent_03

Question: What is the recommended treatment for migraine headaches?

Answer: I don't know based on these documents.

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 631, "excerpt": "to protect ground and surface water quality; buffer strips, oil/\ngrease separators or other recommended techniques for park ing\narea drainage systems; grease traps and other recommended\ntechnologies for facilities such as golf cart maintenance o r wash\nareas to prevent untreated runoff from entering the natural\naquatic environmental berms, vegetative strips, grease tr aps, or\nother recommended technologies in parking areas for draina ge\ncontrols to minimize pollution to nearby riparian areas ad "}, {"source": "zoning-ordinance-082024-rev.pdf", "page": 16, "excerpt": "treatment, but where there is no overnight lodging. \n \n3-52 Club, or Lodge, private. All incorporated or un-incorporated associations for civic, \nsocial, cultural, religious, fraternal, literary, political, and recreational or like activities \noperated for the benefit of its members and not open to the general public. \n \n3-53 Reserved. (Ordinance 2023-01; 05/16/23)"}, {"source": "zoning.pdf", "page": 12, "excerpt": "Director will determine the definition of Site. In a mixed use development with different FAR \nlimits, the FAR will be the use with the majority square footage.  For example, if 50.6 % of the \nbuilding area is residential, then the whole project will use the residential FAR. \n \nC. Base FAR. The base FAR is what is allowable by right in each district.  The base FAR may not \nbe exceeded without providing significant amenities as defined in Chapter 5.0 Density Bonus \nProgram. \n \nD. Minimum FAR. The"}]

### held_ambiguous_01

Question: What is the maximum fence height?

Answer: Which city or document do you mean?

Sources: []
