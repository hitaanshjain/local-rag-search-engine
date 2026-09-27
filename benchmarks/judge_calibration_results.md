# Citation-support judge calibration

Run at: 2026-09-27T08:45:30.884868+00:00
Judge: `qwen2.5:7b`.

Agreement with hand labels: 73% (22 pairs).

| Expected | Agreement |
|---|---:|
| partial | 20% |
| supported | 86% |
| unsupported | 90% |

| ID | Expected | Judge label | Sentence |
|---|---|---|---|
| cal_01 | supported | supported | A guest house is limited to 900 square feet. |
| cal_02 | unsupported | unsupported | A guest house is limited to 700 square feet. |
| cal_03 | unsupported | unsupported | A guest house is limited to 900 square meters. |
| cal_04 | supported | partial | A Charleston home occupation may have one full-time or part-time nonresident employee working at the residence. |
| cal_05 | unsupported | partial | A Charleston home occupation may have two nonresident employees working at the residence. |
| cal_06 | supported | supported | A guest house may not be rented out. |
| cal_07 | unsupported | unsupported | A guest house may be used for rental purposes. |
| cal_08 | partial | partial | A guest house is limited to 900 square feet and may contain no more than two bedrooms. |
| cal_09 | unsupported | unsupported | A guest house is limited to 900 square feet. |
| cal_10 | partial | supported | A Charleston home occupation may have no exterior sign. |
| cal_11 | unsupported | unsupported | Truck cabs may be used in connection with a Charleston home occupation. |
| cal_12 | supported | supported | Music instruction at a Charleston home occupation is limited to two students at a time. |
| cal_13 | unsupported | unsupported | A Charleston home occupation may have one full-time or part-time nonresident employee working at the residence. |
| cal_14 | supported | supported | Surface parking in a P zone combined with an A or R zone requires a 10 ft. front yard. |
| cal_15 | unsupported | unsupported | The OS zone requires a 10 ft. front yard. |
| cal_16 | partial | supported | A P zone requires no front yard. |
| cal_17 | supported | supported | In a mixed use development with different FAR limits, the use with the majority of the square footage sets the FAR. |
| cal_18 | partial | supported | The minimum FAR applies to all new development and redevelopment in the Urban Core zone. |
| cal_19 | unsupported | unsupported | The minimum FAR applies to sites totaling five contiguous acres or more outside the Urban Core zone. |
| cal_20 | supported | supported | In the MIC District, a hospital or clinic is permitted by right. |
| cal_21 | unsupported | unsupported | All development regulations of the B-3 zoning district apply in the MIC District. |
| cal_22 | partial | unsupported | In the MIC District, a drugstore and a car wash are both permitted by right. |
