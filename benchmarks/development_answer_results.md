# Development answer evaluation

Run at: 2026-09-27T05:17:57.228550+00:00
Git HEAD at run: `ce0bd071fe78e310c49169035b0a7d7bd960fe99` (worktree changes may have been present).
Dataset: `development_queries.json`.
Models: `llama3.2:3b` and `nomic-embed-text`.
Queries: 12 (8 answerable, 3 unanswerable, 1 ambiguous).

Automated checks passed: 9/12.

Answerable items pass when the answer contains an accepted phrase and cites the labeled physical PDF page. Unanswerable items require the exact abstention. The ambiguous item requires a clarification question. These are screening checks, not proof that every sentence is factually supported. The no-answer and ambiguity labels are task expectations, not exhaustive corpus proofs.

## Per-query results

| ID | Kind | Fact/behavior | Labeled page citation | Valid refs | Pass |
|---|---|---:|---:|---:|---:|
| held_iss_01 | answerable | True | True | True | True |
| held_sum_01 | answerable | False | True | True | False |
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
P2 = Permitted with Level 2 Review. [1]

Sources: [{"source": "zoning.pdf", "page": 5, "excerpt": "1. Permitted Uses:  P = PERMITTED; P(Number) = PERMITTED with Level of Review \n(0, 1, 2, 3) [i.e. P2 = Permitted with Level 2 Review]; Empty box = NOT PERMITTED. \n2. Unclassified Uses. Those uses which are not listed on the table below but are listed in IMC \n18.06.130, Table of Permitted Land Uses, are Not Permitted in any Central Issaquah zone.  \nThose remaining uses which are not listed on the table below and are also not listed in IMC \n18.06.130, Table of Permitted Land Uses, shall be determi", "extraction_method": "text"}, {"source": "zoning.pdf", "page": 4, "excerpt": "18\n\nTable 4.2B Intent of Overlays\n\nOverlay \nIntent\n\nCentral Plan\n\nDistrict(s) \nVertical \nMixed Use\n\nThe intent is to establish an overlay within the Urban Core where \nviable mixed use development is required. Where parcels shown to \nhave Required Ground Floor Frontages as indicated in Figure 4B \nCentral Issaquah Vertical Mixed Use Overlay map, buildings are \nrequired to be a minimum of two floors with the ground floor of \nbuildings comprised of active uses that ensure a dense, vibrant, \npedestri", "extraction_method": "text"}, {"source": "zoning.pdf", "page": 11, "excerpt": "in Central Issaquah. The District Standards Table found in IMC 18.07.360 does not apply in the \nCentral Issaquah zoning districts. Each structure, development, or activity in a Central Issaquah \nzoning district shall comply with these requirements except as otherwise provided in this \nSection. \n \nB. Floor Area Ratio.  The relationship between the amount of Gross Floor Area in a Building (or\n\nBuildings) and the Developable Site Area on which the Building(s) stands.  It is obtained by \ndividing th", "extraction_method": "text"}]

### held_sum_01

Question: How much front yard does a surface parking zone need when it is combined with an agricultural or residential zone in the generalized summary?

Answer: Jurisdiction: Los Angeles | District: not specified | Document version: Adopted December 3, 2013 | Source: E Generalized Summary of Zoning Regulations.pdf
For a surface parking zone combined with an A or R Zone, there is no required front yard. [1]

Sources: [{"source": "E Generalized Summary of Zoning Regulations.pdf", "page": 6, "excerpt": "Appendix E Generalized Summary of Zoning Regulations \b\n\u0003Housing Element 2013–2021 - Appendices\n\nMaximum Height\nRequired yards\nMinimum\n\nMin.\n\nZone\nUse\n\nLot \nWidth\nStories\nFeet\nFront\nSide\nRear\n\nArea Per \nLot/ Unit\n\nParking\n\nAutomobile Parking–Surface and\n\nUnderground \nSurface Parking; \nLand in a P Zone may also be\n\n10 ft. in combination \nwith an A or R Zone;\n\nnone\nnone, unless also in\n\nP\n\nan A or R Zone\n\notherwise none\n\nClassified in A or R Zone\n\nunlimited (8)\n\n5 ft. + 1 ft. each \nstory above 2nd\n", "extraction_method": "text"}, {"source": "E Generalized Summary of Zoning Regulations.pdf", "page": 5, "excerpt": "Zone\nUse\n\nMaximum Height\nRequired yards\nMinimum\n\nArea Per \nLot/ Unit\n\nMin.\n\nLot \nWidth\nStories\nFeet\nFront\nSide\nRear\n\nManufacturing\n\nMR1\n\nRestricted Industrial \nCM Uses, Limited Commercial \nandManufacturing, Clinics,  \nMedia Products, \nLimited Machine Shops, Animal \nHospitals and Kennels\n\nunlimited (8)\n\n5 ft. for lots <100 \nft. deep; 15 ft. for \nlots >100 ft. deep\n\nnone for industrial\n\nor commercial\n\nuses;same as\n\nR4 zone for \nresidential uses (5)\n\nnone for industrial\n\nor commercial \nuses; same a", "extraction_method": "text"}, {"source": "E Generalized Summary of Zoning Regulations.pdf", "page": 7, "excerpt": "Housing Element 2013–2021 - Appendices\b\nAppendix E Generalized Summary of Zoning Regulations\n\nTransitional Height: \nPortions of buildings in C or M zones within certain distances of RW1 or more restrictive zones shall not exceed the \nfollowing height limits, in accordance with Section 12.21.1 A 10 of the Zoning Code:\n\nDistance (ft)\nHeight (ft)\n\n0–49\n25\n50–99\n33\n100–199\n61\n\nZone Prefixes \n(Section 12.32 of the Zoning Code)\n\n(T), [T], T\nTentative Zone Classification\nCity Council requirements for p", "extraction_method": "text"}]

### held_urb_01

Question: In Urbana, how far must a proposed gaming hall be from another licensed gaming hall?

Answer: Jurisdiction: Urbana | District: not specified | Document version: not identified | Source: article_v_-_use_regulations.pdf
In Urbana, a proposed gaming hall must be at least 500 feet from any other licensed gaming hall. [1]

Sources: [{"source": "article_v_-_use_regulations.pdf", "page": 16, "excerpt": "****See Table VII-1 for Standards for Specific Conditional Uses\n\n***** The establishment requesting a license for a principal use gaming hall shall be a minimum of five hundred feet from any other licensed \ngaming hall or pre-existing Day Care Facility, Day Care Home, School, or Place of Worship, as defined under the Religious Corporation Act \n(805 ILCS 110/0.01 et seq.). The establishment requesting a license for a principal use gaming hall shall also be a minimum of two \nhundred and fifty feet", "extraction_method": "text"}]

### held_uni_01

Question: What minimum lot size does Union City require for a cemetery?

Answer: Jurisdiction: Union City, Georgia | District: GC | Document version: August 20, 2024, Rev. | Source: zoning-ordinance-082024-rev.pdf
The minimum lot area for a cemetery in Union City is ten (10) acres [1].

Sources: [{"source": "zoning-ordinance-082024-rev.pdf", "page": 100, "excerpt": "acre of development. (Ordinance 2001-12, October 16, 2001)\n\n13. Cemetery, provided: \n \na. Minimum lot area shall be ten (10) acres;\n\nb. Gravesites shall be set back at least 50 feet from all property lines;", "extraction_method": "text"}, {"source": "zoning-ordinance-082024-rev.pdf", "page": 76, "excerpt": "separated from any such property line, excluding the front property line, by a \nplanted buffer strip; and\n\nc. Accessory schools and cemeteries are permissible provided an additional three\n\n(3) acres is provided in addition to the three (3) acre church requirement.\n\n3. Schools and their customary related uses, provided: \n \na. Minimum lot size is three (3) acres;\n\nb. Minimum lot frontage is at least 200 feet;\n\nc. All buildings are located on a lot fronting a major or collector street, as\n\ndetermin", "extraction_method": "text"}, {"source": "zoning-ordinance-082024-rev.pdf", "page": 63, "excerpt": "c. Accessory schools and cemeteries are permissible provided an additional three\n\n(3) acres is provided in addition to the three (3) acre church requirement.\n\n7. Schools and their customary related uses, provided: \n \na.  Minimum lot size is three (3) acres;\n\nb. Minimum lot frontage is at least 200 feet;\n\nc. All buildings are located on a lot fronting a major or collector street, as\n\ndetermined by the Planning Commission; and\n\nd. All buildings are placed not less than 50 feet from any property li", "extraction_method": "text"}]

### held_uni_02

Question: Does Union City's R-2 district list noncommercial agriculture among its permitted uses?

Answer: Jurisdiction: Union City, Georgia | District: R-2 | Document version: August 20, 2024, Rev. | Source: zoning-ordinance-082024-rev.pdf
Yes, non-commercial agriculture is listed as a permitted use in Union City's R-2 district. [1]

Sources: [{"source": "zoning-ordinance-082024-rev.pdf", "page": 53, "excerpt": "6-2 R-2 Single-Family Residential.\n\nA. Description of District. \nThe R-2 single-family residential district is intended to provide \nsuitable open areas for single-family, detached dwellings at low to moderate densities, \nwith access to public water and sewerage. \n \nB. Permitted Uses. \nWithin the R-2 Zoning District, the following Permitted uses shall be \nallowed:\n\n1. Single-family detached dwellings; \n \n2. Accessory buildings and uses;\n\n3. Clubs and recreation uses when part of the overall resid", "extraction_method": "text"}]

### held_cha_01

Question: What is the minimum height for a principal structure in Charleston's 55/30 height district?

Answer: Jurisdiction: not identified | District: not specified | Document version: Supplement No. 25, November 2025 | Source: Charleston, SC Zoning.pdf
The minimum height for a principal structure in Charleston's 55/30 height district is thirty (30) feet [1].

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 405, "excerpt": "3. \nAll principal structures fifty (50) feet or less in height shall have no set back from \nstreet right-of-way lines, subject to provisions of Article 3: Part 10; except such \nstructures may be set back from street right-of-way a distance no greater than the \nleast such set back of the two adjoining buildings on either side. \n(Ord. No. 2017-085, § 1, 8-15-17; Ord. No. 2020-014, § 1, 1-28-20)\n\nSec. 54-306.V. Height District 55/30 S.\n\nIn this district:\n\n1. \nNo part of a structure shall exceed the", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 406, "excerpt": "§ 54-306.V \n § 54-306.X\nCHARLESTON ZONING ORDINANCE\n\n2. \nAll structures shall have no minimum set back from street right-of-way lines, subject \nto provisions of Article 3: Part 10. \n(Ord. No. 2017-085, § 1, 8-15-17; Ord. No. 2020-014, § 1, 1-28-20)\n\nSec. 54-306.W. Height District 55/30.\n\nIn this district:\n\n1. \nNo part of a structure shall exceed the height of fifty-five (55) feet, nor shall the \nprincipal structure be lower than thirty (30) feet.\n\n2. \nAll structures shall have no set back from s", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 379, "excerpt": "Sec. 54-306.P. Height District 80/30. \nSec. 54-306.Q. Height District 50W. \nSec. 54-306.R. Height District W. \nSec. 54-306.S. Height District WP. \nSec. 54-306.T. Height District 56/30 V. \nSec. 54-306.U. Height District 120/30. \nSec. 54-306.V. Height District 55/30 S. \nSec. 54-306.W. Height District 55/30. \nSec. 54-306.X. Height district chart. \nSec. 54-306.Y. Height District 8-12(A), (B), and (C). \nSec. 54-307. \nView corridor protection. \nSec. 54-308. \nExceptions. \nSec. 54-309. \nReserved.", "extraction_method": "text"}]

### held_cha_02

Question: For a Charleston development with at least twenty business units, what is the per-face area limit for its monument sign?

Answer: Jurisdiction: Charleston, South Carolina | District: not specified | Document version: Supplement No. 25, November 2025 | Source: Charleston, SC Zoning.pdf
For a Charleston development with at least twenty business units, the per-face area limit for its monument sign is one hundred (100) square feet. [2]

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 504, "excerpt": "2.\nFor a development containing more than three (3) business units and fewer\nthan twenty (20) business units, one (1) monument sign shall be permitted as\nfollows:\n\n(a)\nNo sign shall exceed sixty (60) square feet per face or one hundred and\ntwenty (120) square feet of total sign face area. No sign shall exceed\nfourteen (14) feet in height.\n\n(b)\nMonument signs may be illuminated internally or with a shielded spot\nlight located at the base of the sign. Plastic face signs shall have opaque\nbackgroun", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 505, "excerpt": "3.\nFor a development containing twenty (20) or more business units, or 150,000\nsquare feet or more of floor area, one (1) monument sign shall be permitted as\nfollows:\n\n(a)\nNo sign shall exceed one hundred (100) square feet per face or two\nhundred (200) square feet of total sign face area. No sign shall exceed\nfourteen (14) feet in height.\n\n(b)\nMonument signs may be illuminated internally or with a shielded spot\nlight located at the base of the sign. Plastic face signs shall have opaque\nbackgroun", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 242, "excerpt": "f.\nSignage. Requirements for signage shall apply per Article 4, Part 3, Sign Regulations\nfor the base zoning district unless noted otherwise below.\n\n1.\nFor a development containing three or fewer business units, one freestanding\nmonument style sign with a maximum height of twelve (12) feet and a maximum\nsize of forty (40) square feet per face shall be allowed.\n\n2.\nFor a development containing more than three business units, one monument\nstyle sign with a maximum height of fourteen feet (14') and", "extraction_method": "text"}]

### held_cha_03

Question: In Charleston, where does someone appeal an administrative decision about a sidewalk cafe permit?

Answer: Jurisdiction: Charleston, South Carolina | District: not specified | Document version: Supplement No. 25, November 2025 | Source: Charleston, SC Zoning.pdf
To appeal an administrative decision about a sidewalk cafe permit in Charleston, an appeal must be filed within ten (10) business days after actual notice of the decision by delivery of the approved appeal form and fee to the Zoning Division office [1].

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 681, "excerpt": "Section 2. Time Limit for Appeal of an Administrative Decision.\n\nAn appeal from an administrative decision must be filed within ten (10) business days after \nactual notice of the decision by delivery of the approved appeal form and fee to the Zoning \nDivision office.\n\nSection 3. Time Limit and Procedure for Appeal for Reconsideration of a Board\n\nDecision to the Board.", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 721, "excerpt": "Section 2. Time of Appeal.\n\nAn appeal from a Board decision or an administrative decision must be filed within fifteen \n(15) days from the making of such decision, order, requirement or determination.\n\nArt. II, § 3 \n Art. III, § 2", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 688, "excerpt": "Section 2. Time for Appeal for an Administrative Decision.\n\nAn appeal from an administrative decision must be filed within fifteen (15) calendar days \nfrom the making of such decision, order, requirement or determination.\n\nSection 3. Calendar.\n\nAppeals shall be marked with the date of receipt and placed on the hearing calendar.\n\nSection 4. Withdrawal of Appeal.\n\nAny appeal may be withdrawn by written notice delivered to the secretary prior to action by \nthe Board. An appeal may not be re-filed a", "extraction_method": "text"}]

### held_absent_01

Question: What is the battery capacity of the 2025 Tesla Model 3?

Answer: I don't know based on these documents.

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 355, "excerpt": "(a)\nThe owner shall execute and provide the Department a restrictive\ncovenant committing to achieve and maintain the specified rating.\n\n(b)\nThe owner shall provide the Department with certified evidence the\nsystem meets the capacity required and is functioning properly before a\ncertificate of occupancy is given.(c) Certificate of occupancy. If the\ncommitted points in this category are not achieved, the owner shall be\nrequired to substitute incentive options and earn all points necessary to\njusti", "extraction_method": "text"}, {"source": "zoning-ordinance-082024-rev.pdf", "page": 24, "excerpt": "A. That has no visible from the exterior of the structure and no other advertising that\n\nindicates a nude or semi-nude person is available for viewing; and\n\nB. Where in order to participate in a class a student must enroll at least three (3) days\n\nin advance of the class; and \n \nC. Where no more than one (1) nude or semi-nude model is on the premises at any one\n\ntime.", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 251, "excerpt": "The Conservation sub-area extends from Battery Island Drive to the Folly River. This\narea is intended to be the least intensely developed area of the overlay zoning district and is\nto provide a natural scenic open space before entering the City of Folly Beach by preserving\nthe marsh views and vistas of this area. This portion of the overlay zoning district is\nintended to provide an appropriate transition from the more intense commercial develop-\nment in the North Village, Commercial Core, and So", "extraction_method": "text"}]

### held_absent_02

Question: Who won the 2024 Nobel Prize in Physics?

Answer: I don't know based on these documents.

Sources: [{"source": "Charleston, SC Zoning.pdf", "page": 201, "excerpt": "8.\nSuch occupation shall be carried on by a resident, members of his family living on\nthe premises, and no more than one full-time or part-time nonresident employee\nwho works at the residence used for the home occupation. The home occupation\nmay have other employees who are not working at the residence, but work at other\noff-site locations, if applicable. For the purpose of this section, the term \"nonresident\nemployee\" includes an employee, business partner, co-owner, or other person\naffiliated ", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 607, "excerpt": "to study and model the drainage conditions in the Basin and to update and implement \nregulations to alleviate flooding conditions there, it is evident that, absent a thorough \nevaluation of the drainage patterns in portions of the Basin, of the development and \ninfrastructure in place, and of development that will reasonably occur in these areas in the \nimmediate future, development in the Basin, both existing and planned, will be threatened, \nas well as the quality of life of those who live and", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 633, "excerpt": "6.\nOnly one full-time or part-time employee, who is not a full-time resident of\nthe home where the bed and breakfast is located, is allowed. For the purpose\nof this provision, the term \"nonresident employee\" includes an employee,\nbusiness partner, co-owner, or other person affiliated with the bed and\nbreakfast, who does not live at the site, but who visits the site as part of the\nbed and breakfast.\n\n7.\nThe operator of the bed and breakfast shall be a full-time resident of the\ndwelling unit.\n\n8.\n", "extraction_method": "text"}]

### held_absent_03

Question: What is the recommended treatment for migraine headaches?

Answer: I don't know based on these documents.

Sources: [{"source": "zoning-ordinance-082024-rev.pdf", "page": 242, "excerpt": "August 20, 2024, Rev. \nPage 233\n\niii. In what way are the extraordinary and exceptional conditions, identified above,\n\npeculiar to the use or development proposed or to the particular piece of \nproperty involved? \n \niv. What conditions, factors and/or circumstances give assurance that if the\n\nrequested variance were granted that such variance would not cause substantial \ndetriment to other property owners or tenants, or to the public good and would \nnot impair the purpose and intent of the ordin", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 535, "excerpt": "a.\nThere is a stormwater management plan which addresses, to the satisfaction of\nthe Board based upon a review of the plan by the Technical Review Committee, the\ndesign, construction, future maintenance and future monitoring of storm water\nrunoff resulting from the development of the Lot, which has been certified by an\nengineer licensed by the State of South Carolina.\n\nb.\nThe project's engineer certifies that the adverse impact on water quality in the\nadjacent water body of the project is equal ", "extraction_method": "text"}, {"source": "Charleston, SC Zoning.pdf", "page": 436, "excerpt": "d.\nReplacement. Replacement is accomplished by planting the number, size and species of\na recommended tree in accordance with the conditions at the Board of Zoning\nAppeals—Site Design, on land under the same ownership which is to be developed\npursuant to the same development permit, within the right-of-way adjacent to the\nproperty subject to the approval of the appropriate government agency, or off-site\nwithin the general area of the trees being replaced.\n\ne.\nTree Planting Requirements. In the r", "extraction_method": "text"}]

### held_ambiguous_01

Question: What is the maximum fence height?

Answer: Which city or document do you mean?

Sources: []
