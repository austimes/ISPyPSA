# Manually extracted template tables: IASR 2026 ISP Final (v7.8)

`load_manually_extracted_tables("7.8")` reads every CSV in this folder: workbook data `isp-workbook-parser` cannot structure.

- `policy_generator_types.csv`: technology label map.
- `custom_constraints_lhs.csv` and `custom_constraints_rhs.csv`: REZ group and transmission limit constraints transcribed
  from the workbook sheet "Build limits - REZs". The right-hand side is the summer-typical limit, or the import limit for
  the hydrogen import constraints. Constraints whose terms do not map to model components (HCC1, MN2, NW1, SNW1, the
  WV1/WV2 WRL variants, SQ1 after Borumba) are left out.
