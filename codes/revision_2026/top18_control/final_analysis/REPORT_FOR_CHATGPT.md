# CAMELS-US 2026 — Top18 Final Control Experiment

Generated: **2026-09-14 06:34**

## 1. Experiment design

- Basins: **531**
- Random seeds: **10**
- Existing compact ensemble: **Top10 = 10 members**
- Extended control ensemble: **Top18 = 18 members**
- Primary aggregation: **median**
- Secondary Top18 aggregation: **mean**
- Test period: **1989-10-01 → 1999-09-30**
- Test length: **3652 daily observations**
- Canonical observations: `Obs_test.p`
- Primary scientific comparison: **Top18-median vs Top10-median**
- Additional comparisons: **Hydrology-informed / Cluster-wise** and **Benchmark**

---

# 2. Headline Top18 vs Top10 results


      metric direction  Top18_median  Top10_median  raw_delta_Top18_minus_Top10  pct_basins_improved  wilcoxon_p
         FHV      zero     -16.96270     -16.37422                     -0.28912             34.65160     0.00000
         FLV      zero      -2.01058      -2.92284                     -0.21994             42.93785     0.02602
         FMS      zero      -7.66534      -6.93598                     -0.65755             54.23729     0.00000
         KGE    higher       0.77450       0.77134                      0.00004             50.28249     0.62699
        MAPE     lower      34.08310      34.72106                     -0.55969             70.43315     0.00061
Missed-Peaks     lower       0.33000       0.33333                      0.00000             34.83992     0.05348
         NSE    higher       0.81450       0.81191                      0.00206             76.27119     0.00000
   Peak-MAPE     lower      34.37680      34.90718                     -0.14209             59.88701     0.00000
 Peak-Timing     lower       0.23810       0.23684                      0.00000             24.85876     0.01774
   Pearson-r    higher       0.91392       0.91240                      0.00125             81.73258     0.00000
        RMSE     lower       1.05635       1.06204                     -0.00611             76.27119     0.00000


Interpretation rule:

- NSE, KGE, Pearson-r: higher is better.
- RMSE, MSE, MAPE, Peak-MAPE, Peak-Timing and Missed-Peaks: lower is better.
- FHV/FMS/FLV are bias-type measures; values closer to zero are preferable.

---

# 3. Full headline comparison table


_Not available._


---

# 4. Overall method ranking



## NSE

      method  count  median    mean     std      min     max
  Top18-mean    531 0.81852 0.77388 0.17346 -1.42041 0.96410
Cluster-wise    531 0.81579 0.77630 0.14463 -0.30765 0.96356
       Top18    531 0.81450 0.77182 0.16447 -1.01996 0.96529
       Top10    531 0.81191 0.76951 0.16146 -0.83094 0.96386
   Benchmark    531 0.79312 0.75521 0.14642 -0.35572 0.94850

## KGE

      method  count  median    mean     std      min     max
   Benchmark    531 0.79075 0.73700 0.21267 -2.26600 0.95206
Cluster-wise    531 0.78620 0.73278 0.19958 -1.50973 0.96663
  Top18-mean    531 0.78600 0.73797 0.19796 -1.25576 0.95754
       Top18    531 0.77450 0.72939 0.19658 -1.02869 0.96013
       Top10    531 0.77134 0.72810 0.20115 -1.19117 0.96161

## RMSE

      method  count  median    mean     std     min     max
  Top18-mean    531 1.04298 1.23203 0.79790 0.08816 5.41558
       Top18    531 1.05635 1.23913 0.80046 0.08171 5.42504
       Top10    531 1.06204 1.24653 0.80331 0.07778 5.44962
Cluster-wise    531 1.06243 1.24705 0.81710 0.06574 5.59815
   Benchmark    531 1.12015 1.31455 0.85650 0.06694 5.64975

## Peak-Timing

      method  count  median    mean     std  min    max
       Top10    531 0.23684 0.36372 0.33394  0.0 2.2500
Cluster-wise    531 0.23810 0.35693 0.32006  0.0 2.0000
       Top18    531 0.23810 0.36026 0.33338  0.0 2.1875
  Top18-mean    531 0.23810 0.35288 0.32979  0.0 2.3125
   Benchmark    531 0.27083 0.38668 0.32686  0.0 2.0000

## Peak-MAPE

      method  count   median     mean      std      min       max
  Top18-mean    531 34.17204 36.87797 14.86519 12.37089 105.43782
       Top18    531 34.37680 37.35605 14.93945 12.62141  94.54410
Cluster-wise    531 34.38868 37.20052 14.87602 12.32235  99.43488
       Top10    531 34.90718 37.53205 15.01800 12.77070  96.29898
   Benchmark    531 35.34739 38.40624 14.69714 14.17347 106.76702


---

# 5. Stability across the 10 random seeds


  seed metric   Top10   Top18  delta_Top18_minus_Top10
191889    KGE 0.77117 0.76866                 -0.00251
191889    NSE 0.81184 0.81503                  0.00319
191889   RMSE 1.07347 1.05880                 -0.01467
307443    KGE 0.77975 0.77913                 -0.00062
307443    NSE 0.81293 0.81608                  0.00315
307443   RMSE 1.06872 1.06184                 -0.00688
328237    KGE 0.77447 0.77142                 -0.00305
328237    NSE 0.81365 0.81489                  0.00124
328237   RMSE 1.06534 1.06444                 -0.00090
385445    KGE 0.77583 0.77215                 -0.00368
385445    NSE 0.80998 0.81314                  0.00317
385445   RMSE 1.06834 1.05871                 -0.00963
473461    KGE 0.77811 0.78018                  0.00208
473461    NSE 0.81326 0.81697                  0.00370
473461   RMSE 1.06419 1.05909                 -0.00510
643969    KGE 0.78104 0.78089                 -0.00015
643969    NSE 0.81450 0.81625                  0.00175
643969   RMSE 1.06797 1.06042                 -0.00756
665980    KGE 0.78457 0.77748                 -0.00709
665980    NSE 0.81295 0.81454                  0.00159
665980   RMSE 1.05681 1.06500                  0.00819
845563    KGE 0.77840 0.77485                 -0.00354
845563    NSE 0.81205 0.81564                  0.00358
845563   RMSE 1.06153 1.06007                 -0.00146
985957    KGE 0.77537 0.77956                  0.00419
985957    NSE 0.80904 0.81579                  0.00675
985957   RMSE 1.05697 1.04583                 -0.01113
993061    KGE 0.77968 0.77705                 -0.00263
993061    NSE 0.81194 0.81407                  0.00213
993061   RMSE 1.06347 1.05636                 -0.00711


---

# 6. Basin-wise sensitivity to increasing ensemble size



## NSE — strongest improvements

  basin   Top18    Top10   delta  improvement
9306242 0.02978 -0.01919 0.04897      0.04897
7299670 0.53920  0.49213 0.04707      0.04707
8109700 0.74978  0.71783 0.03195      0.03195
6406000 0.53185  0.50455 0.02730      0.02730
2046000 0.68401  0.65791 0.02610      0.02610
7208500 0.51796  0.49209 0.02587      0.02587
4105700 0.55038  0.52468 0.02570      0.02570
5120500 0.34050  0.31682 0.02369      0.02369
1466500 0.69816  0.67712 0.02104      0.02104
5291000 0.51968  0.50045 0.01923      0.01923

## NSE — strongest deteriorations

  basin    Top18    Top10    delta  improvement
9484600 -1.01996 -0.83094 -0.18902     -0.18902
7301410  0.31960  0.38860 -0.06900     -0.06900
8165300  0.40352  0.43378 -0.03026     -0.03026
8195000  0.73988  0.75515 -0.01527     -0.01527
6332515  0.33577  0.35053 -0.01476     -0.01476
8196000  0.54882  0.56132 -0.01249     -0.01249
8086290  0.61656  0.62812 -0.01157     -0.01157
9512280  0.74242  0.75390 -0.01148     -0.01148
7195800  0.70725  0.71810 -0.01084     -0.01084
7261000  0.59476  0.60429 -0.00953     -0.00953

## KGE — strongest improvements

  basin    Top18    Top10   delta  improvement
8202700 -1.02869 -1.19117 0.16248      0.16248
6847900  0.13340  0.01606 0.11734      0.11734
6350000  0.08998  0.02412 0.06586      0.06586
9306242  0.33858  0.27420 0.06438      0.06438
9447800 -0.05081 -0.11095 0.06015      0.06015
6344600  0.16103  0.10277 0.05826      0.05826
6477500  0.40399  0.34587 0.05813      0.05813
7299670  0.67161  0.61585 0.05576      0.05576
7142300  0.21415  0.16087 0.05327      0.05327
8086212  0.42924  0.37704 0.05220      0.05220

## KGE — strongest deteriorations

   basin    Top18    Top10    delta  improvement
 9484600 -0.58921 -0.30836 -0.28084     -0.28084
11151300  0.63294  0.71966 -0.08672     -0.08672
 9497980  0.72126  0.76353 -0.04226     -0.04226
 8150800  0.44698  0.48818 -0.04120     -0.04120
 8189500  0.60567  0.63292 -0.02724     -0.02724
 2059500  0.74563  0.76906 -0.02343     -0.02343
 7195800  0.59582  0.61884 -0.02302     -0.02302
 8269000  0.74630  0.76704 -0.02075     -0.02075
 2296500  0.82327  0.84342 -0.02014     -0.02014
 9035900  0.82003  0.83940 -0.01937     -0.01937

## RMSE — strongest improvements

   basin   Top18   Top10    delta  improvement
12115000 3.10157 3.17007 -0.06850      0.06850
12114500 2.66494 2.72265 -0.05772      0.05772
 6921200 1.82991 1.88471 -0.05481      0.05481
12143600 2.66822 2.72209 -0.05387      0.05387
10336645 1.17837 1.23039 -0.05202      0.05202
11230500 1.16251 1.21199 -0.04948      0.04948
14138800 4.03385 4.07972 -0.04587      0.04587
10343500 1.28600 1.32953 -0.04353      0.04353
11148900 2.12533 2.16879 -0.04347      0.04347
10336660 2.72214 2.76491 -0.04276      0.04276

## RMSE — strongest deteriorations

   basin   Top18   Top10   delta  improvement
 5595730 1.95619 1.90217 0.05402     -0.05402
11475560 4.00091 3.95662 0.04429     -0.04429
 7375000 2.67857 2.64874 0.02983     -0.02983
 2140991 1.19390 1.16565 0.02826     -0.02826
 7195800 1.36242 1.33693 0.02549     -0.02549
 2108000 0.88107 0.85681 0.02426     -0.02426
 2128000 2.17648 2.15259 0.02389     -0.02389
 8195000 0.77414 0.75107 0.02307     -0.02307
 7261000 1.93864 1.91571 0.02293     -0.02293
 2415000 1.04483 1.02236 0.02247     -0.02247


---

# 7. Hydrological-cluster / hydrology-informed analysis


 cluster       method      metric  count  median    mean     std
       1    Benchmark         KGE     83 0.74907 0.68922 0.19222
       1    Benchmark         NSE     83 0.74303 0.71187 0.13796
       1    Benchmark Peak-Timing     83 0.25000 0.35116 0.35387
       1    Benchmark        RMSE     83 1.15239 1.24821 0.56702
       1 Cluster-wise         KGE     83 0.74145 0.68329 0.20174
       1 Cluster-wise         NSE     83 0.76033 0.73258 0.14378
       1 Cluster-wise Peak-Timing     83 0.22222 0.33392 0.34747
       1 Cluster-wise        RMSE     83 1.07259 1.18807 0.54872
       1        Top10         KGE     83 0.74497 0.68348 0.20168
       1        Top10         NSE     83 0.77000 0.72930 0.15296
       1        Top10 Peak-Timing     83 0.21053 0.33424 0.36485
       1        Top10        RMSE     83 1.07564 1.18436 0.53950
       1        Top18         KGE     83 0.72783 0.68449 0.19191
       1        Top18         NSE     83 0.76945 0.73249 0.15102
       1        Top18 Peak-Timing     83 0.21053 0.32674 0.35589
       1        Top18        RMSE     83 1.07308 1.17843 0.54060
       1   Top18-mean         KGE     83 0.73972 0.69867 0.18394
       1   Top18-mean         NSE     83 0.77055 0.73673 0.14834
       1   Top18-mean Peak-Timing     83 0.22222 0.32599 0.36680
       1   Top18-mean        RMSE     83 1.05635 1.17007 0.53781
       2    Benchmark         KGE    195 0.81153 0.79459 0.08391
       2    Benchmark         NSE    195 0.80001 0.78289 0.08413
       2    Benchmark Peak-Timing    195 0.18421 0.22331 0.16640
       2    Benchmark        RMSE    195 1.14895 1.27746 0.56424
       2 Cluster-wise         KGE    195 0.79859 0.78698 0.09216
       2 Cluster-wise         NSE    195 0.81836 0.80110 0.08251
       2 Cluster-wise Peak-Timing    195 0.16667 0.21287 0.17292
       2 Cluster-wise        RMSE    195 1.09515 1.22093 0.55176
       2        Top10         KGE    195 0.79471 0.78397 0.09291
       2        Top10         NSE    195 0.81629 0.79945 0.08100
       2        Top10 Peak-Timing    195 0.16667 0.21362 0.18764
       2        Top10        RMSE    195 1.10978 1.22381 0.54761
       2        Top18         KGE    195 0.79709 0.78295 0.09444
       2        Top18         NSE    195 0.81990 0.80131 0.08100
       2        Top18 Peak-Timing    195 0.16667 0.21334 0.18598
       2        Top18        RMSE    195 1.11417 1.21826 0.54740
       2   Top18-mean         KGE    195 0.80439 0.79016 0.09123
       2   Top18-mean         NSE    195 0.82167 0.80350 0.08062
       2   Top18-mean Peak-Timing    195 0.16667 0.21101 0.18606
       2   Top18-mean        RMSE    195 1.09944 1.21185 0.54498
       3    Benchmark         KGE     67 0.53134 0.47326 0.41438
       3    Benchmark         NSE     67 0.62215 0.56905 0.22639
       3    Benchmark Peak-Timing     67 0.45000 0.54113 0.37926
       3    Benchmark        RMSE     67 0.69866 0.80668 0.64501
       3 Cluster-wise         KGE     67 0.56450 0.48507 0.35237
       3 Cluster-wise         NSE     67 0.68218 0.59974 0.22986
       3 Cluster-wise Peak-Timing     67 0.36364 0.49205 0.38196
       3 Cluster-wise        RMSE     67 0.65462 0.76668 0.62143
       3        Top10         KGE     67 0.56041 0.46023 0.34316
       3        Top10         NSE     67 0.63499 0.56720 0.27717
       3        Top10 Peak-Timing     67 0.40000 0.51055 0.38056
       3        Top10        RMSE     67 0.68721 0.77736 0.61620
       3        Top18         KGE     67 0.56149 0.47117 0.33593
       3        Top18         NSE     67 0.64337 0.56787 0.29248
       3        Top18 Peak-Timing     67 0.40000 0.52238 0.38940
       3        Top18        RMSE     67 0.67583 0.77218 0.61195
       3   Top18-mean         KGE     67 0.58394 0.48307 0.35909
       3   Top18-mean         NSE     67 0.66767 0.56625 0.33147
       3   Top18-mean Peak-Timing     67 0.40000 0.50795 0.37225
       3   Top18-mean        RMSE     67 0.67000 0.76628 0.60907
       4    Benchmark         KGE     61 0.86905 0.85677 0.06008
       4    Benchmark         NSE     61 0.86175 0.85964 0.04866
       4    Benchmark Peak-Timing     61 0.22727 0.22881 0.09994
       4    Benchmark        RMSE     61 2.67533 2.68454 1.09529
       4 Cluster-wise         KGE     61 0.86443 0.85332 0.06522
       4 Cluster-wise         NSE     61 0.88017 0.87859 0.04413
       4 Cluster-wise Peak-Timing     61 0.17500 0.20117 0.11366
       4 Cluster-wise        RMSE     61 2.45120 2.50451 1.05943
       4        Top10         KGE     61 0.86836 0.85650 0.06266
       4        Top10         NSE     61 0.88189 0.88141 0.04348
       4        Top10 Peak-Timing     61 0.18750 0.19650 0.11447
       4        Top10        RMSE     61 2.44640 2.47181 1.03970
       4        Top18         KGE     61 0.86685 0.85684 0.06354
       4        Top18         NSE     61 0.88295 0.88280 0.04353
       4        Top18 Peak-Timing     61 0.18421 0.19698 0.11413
       4        Top18        RMSE     61 2.40902 2.45675 1.03648
       4   Top18-mean         KGE     61 0.86651 0.85898 0.06155
       4   Top18-mean         NSE     61 0.88336 0.88366 0.04347
       4   Top18-mean Peak-Timing     61 0.18182 0.19287 0.12053
       4   Top18-mean        RMSE     61 2.39518 2.44832 1.03382
       5    Benchmark         KGE     66 0.82199 0.80686 0.09005
       5    Benchmark         NSE     66 0.85821 0.83518 0.10077
       5    Benchmark Peak-Timing     66 0.75000 0.76645 0.30580
       5    Benchmark        RMSE     66 0.65609 0.87273 0.61296
       5 Cluster-wise         KGE     66 0.81797 0.80375 0.09366
       5 Cluster-wise         NSE     66 0.87199 0.85681 0.08739
       5 Cluster-wise Peak-Timing     66 0.67424 0.68566 0.31987
       5 Cluster-wise        RMSE     66 0.61709 0.81859 0.58125
       5        Top10         KGE     66 0.81120 0.80175 0.08867
       5        Top10         NSE     66 0.87015 0.84951 0.09590
       5        Top10 Peak-Timing     66 0.71111 0.69207 0.31872
       5        Top10        RMSE     66 0.63387 0.82456 0.57314
       5        Top18         KGE     66 0.81267 0.80434 0.08743
       5        Top18         NSE     66 0.87512 0.85326 0.09422
       5        Top18 Peak-Timing     66 0.65000 0.67999 0.34022
       5        Top18        RMSE     66 0.62645 0.81435 0.56635
       5   Top18-mean         KGE     66 0.82204 0.80997 0.08432
       5   Top18-mean         NSE     66 0.87760 0.85474 0.09738
       5   Top18-mean Peak-Timing     66 0.64853 0.64511 0.33072
       5   Top18-mean        RMSE     66 0.62109 0.80888 0.56400
       6    Benchmark         KGE     59 0.72595 0.71139 0.11487
       6    Benchmark         NSE     59 0.75529 0.73867 0.09409
       6    Benchmark Peak-Timing     59 0.50000 0.53963 0.30750
       6    Benchmark        RMSE     59 0.98012 1.18503 0.72560
       6 Cluster-wise         KGE     59 0.71737 0.70053 0.12725
       6 Cluster-wise         NSE     59 0.77496 0.76055 0.09489
       6 Cluster-wise Peak-Timing     59 0.45455 0.50533 0.32988
       6 Cluster-wise        RMSE     59 0.90368 1.14110 0.72153
       6        Top10         KGE     59 0.69951 0.69529 0.12509
       6        Top10         NSE     59 0.76755 0.75170 0.10072
       6        Top10 Peak-Timing     59 0.43478 0.54015 0.36767
       6        Top10        RMSE     59 0.90736 1.14706 0.71451
       6        Top18         KGE     59 0.69617 0.69318 0.12525
       6        Top18         NSE     59 0.77172 0.75548 0.09887
       6        Top18 Peak-Timing     59 0.43478 0.52005 0.36082
       6        Top18        RMSE     59 0.88643 1.14007 0.71370
       6   Top18-mean         KGE     59 0.71082 0.70456 0.12221
       6   Top18-mean         NSE     59 0.77431 0.76004 0.09717
       6   Top18-mean Peak-Timing     59 0.43478 0.52206 0.37797
       6   Top18-mean        RMSE     59 0.87803 1.13057 0.70954


---

# 8. Water-year analysis


_Not available._


---

# 9. Seasonal analysis


_Not available._


---

# 10. High-flow event analysis


_Not available._


---

# 11. Metric-protocol reproduction audit

Before computing the new Top18 metrics, the pipeline attempts to reproduce
the existing Top10 metrics using the same canonical observations.


 clip mape_mode  nh_mean_absdiff  nh_max_absdiff  mape_mean_absdiff  mape_max_absdiff
False   epsilon              0.0             0.0                0.0               0.0
False   nonzero              0.0             0.0                0.0               0.0
False  positive              0.0             0.0                0.0               0.0
 True   epsilon              0.0             0.0                0.0               0.0
 True   nonzero              0.0             0.0                0.0               0.0
 True  positive              0.0             0.0                0.0               0.0


---

# 12. Audit / unresolved items


## Normalized high-flow bins

```json
{
  "old_artifact_exists": true,
  "exact_top18_reproduction": false,
  "reason": "Exact Top18 normalized-bin extension not auto-generated because the original bin-construction code is not present in the supplied training notebook. Existing artifact preserved; no new bin definition is invented.",
  "old_size_gb": 1.1450850199908018
}
```

No additional ATTENTION markers detected in the audit files.


---

# 13. Files available for detailed review

The accompanying ZIP intentionally excludes giant raw pickles and cache
arrays. It contains the numerical tables, audit files and figures needed
to assess the scientific result.

