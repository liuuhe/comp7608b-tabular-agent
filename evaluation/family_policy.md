# Operational task-family boundary, fixed before test inference

The experiment evaluates new analysis requests on familiar datasets. It does not claim
unseen datasets, unseen pandas primitives, or unseen aggregation/plotting algorithms.
Family separation concerns the substantive analytical question and measured quantity.

Two tasks overlap when development attempted the same substantive target and estimation
or association template and the test differs principally in wording, dates, subset,
category labels, sorting or display. Failed attempts count as exposure. Broad exploratory
development prompts require checking actual attempted plans as well as their text.

An elementary operation alone (grouped count, sum, mean, ratio, scatter, histogram), an
additional grouping dimension, or common dataset fields does not settle the boundary.
For example, mean rental demand by season and mean humidity by season estimate different
quantities for different purposes; weather-field associations share a purpose even when
the selected weather pair changes. Similarly, summing or averaging the same capital-gain
measure across demographic categories is conservatively treated as development exposure.

For the revised catalog, the proposed substantive targets are:

* Retail development: positive-sale revenue and units, country/product demand ranking.
  Test: cancellation record/price audit; line-price summaries and anomalies; calendar
  transaction-record activity; price distributions and price/quantity associations.
* Bike development: mean total demand over time/weather, attempted hourly record counts,
  associations between weather variables and with total demand.
  Test: casual/registered component composition and co-variation; weather levels over
  calendar categories; demand distribution in inclement conditions. Component quantities
  and their shares are distinct from total-demand means; weather levels are distinct
  from demand responses. Rehearsed weather-pair associations and temporal record coverage
  have been removed from the test catalog.
* Adult development: hours/age/education means, category frequencies and missingness,
  capital-gain comparisons, and failed category/weight ratios used as quality measures.
  Test: final-weight sums/means as the measured quantity; education-label/code mapping;
  capital-loss occurrence and its relations to gains and supplied weights; oldest-age
  distribution. The age/education association was removed after its overlap with a
  development grouped-age comparison was identified. Weight-description exploration was removed because its
  boundary with the failed ratios was unresolved. General category-composition
  exploration and capital-gain magnitude comparisons have also been removed.

These proposed boundaries are reviewable claims, not an instruction to approve tasks.
An auditor should flag a concrete same-target/template rehearsal, explain which attempted
analysis establishes it, and retain uncertainty if the evidence does not resolve it.
Changing a family name cannot cure exposure. The final report must describe this scope
and the audit disagreements; it must not imply that different requests imply statistically
independent observations. Related test tasks and variants remain grouped for resampling.
Conservatively merge all retail price/cancellation/distribution tasks into one connected
family and all bike component-total/share/co-variation tasks into another. Broad test
exploration can connect narrower tests even without development leakage. These mergers
reduce the number of resampling units and hence the strength of uncertainty estimates.
