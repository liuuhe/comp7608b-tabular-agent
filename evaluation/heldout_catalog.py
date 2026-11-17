"""Draft held-out questions and independently reviewable reference specifications.

Never imported by the agent. Do not tune prompts against outcomes on these questions.
Task-family assignments remain subject to team review before the experimental freeze.
"""


def catalog():
    tasks, specs = [], {}

    def add(identifier, dataset, family, category, question, **spec):
        chart = spec.pop("chart", None)
        task = dict(
            id=identifier, split="test", dataset=dataset, family=family,
            category=category, question=question,
        )
        if chart:
            task["chart"] = chart
        tasks.append(task)
        if category != "exploration":
            specs[identifier] = spec

    cancelled = [("InvoiceNo", "starts_with", "C")]
    positive = [("Quantity", "gt", 0), ("UnitPrice", "gt", 0),
                ("InvoiceNo", "not_starts_with", "C")]
    add("R01", "retail", "retail_cancellations", "explicit",
        "Count cancelled transaction records by Country: InvoiceNo starts with C. "
        "Count records, not distinct invoices; exclude missing Country, sort Country ascending.",
        operation="rows", groups=["Country"], filters=cancelled)
    add("R02", "retail", "retail_prices", "explicit",
        "For all positive sales (Quantity>0, UnitPrice>0, InvoiceNo not starting with C), "
        "compute unweighted mean UnitPrice in GBP per line by Country, with valid counts. "
        "Drop missing Country and UnitPrice, sort Country ascending. Do not weight by Quantity.",
        operation="mean", column="UnitPrice", groups=["Country"], filters=positive)
    add("R03", "retail", "retail_cancellations", "explicit",
        "For InvoiceNo starting with C, compute unweighted mean UnitPrice by Country. "
        "Include valid UnitPrice counts, keep zero and negative prices, drop missing "
        "Country or UnitPrice, and sort Country ascending. UnitPrice is GBP per unit; "
        "this is a per-line mean of unit prices, not cancellation units or revenue.",
        operation="mean", column="UnitPrice", groups=["Country"], filters=cancelled)
    add("R04", "retail", "retail_record_activity", "explicit",
        "Count transaction records for each calendar month of 2011, including cancellations "
        "and zero-price rows. Parse InvoiceDate; derive InvoiceMonth (1..12). "
        "Use 2011-01-01 inclusive to 2012-01-01 exclusive, sort InvoiceMonth ascending.",
        operation="rows", groups=["InvoiceMonth"], dates=["InvoiceDate"],
        derive_month={"InvoiceMonth": "InvoiceDate"},
        filters=[("InvoiceDate", "ge", "2011-01-01"), ("InvoiceDate", "lt", "2012-01-01")])
    add("R05", "retail", "retail_prices", "visualization",
        "Across all positive sales (Quantity>0, UnitPrice>0, InvoiceNo not starting with C), "
        "bar-chart the eight countries with highest unweighted mean UnitPrice per transaction "
        "line. Use Country, GBP per line and valid counts. Exclude missing Country; sort mean "
        "descending, ties Country ascending. This is not a Quantity-weighted price.",
        operation="mean", column="UnitPrice", groups=["Country"], filters=positive,
        sort=["value", "Country"], ascending=[False, True], limit=8, chart="bar")
    add("R06", "retail", "retail_record_activity", "visualization",
        "Draw a line chart of monthly transaction-record counts in 2011, including cancellations "
        "and zero-price rows. Parse InvoiceDate; derive InvoiceMonth (1..12). Select "
        "2011-01-01 inclusive to 2012-01-01 exclusive, sort InvoiceMonth ascending. "
        "Y axis is transaction records, not distinct invoices or units.",
        operation="rows", groups=["InvoiceMonth"], dates=["InvoiceDate"],
        derive_month={"InvoiceMonth": "InvoiceDate"},
        filters=[("InvoiceDate", "ge", "2011-01-01"), ("InvoiceDate", "lt", "2012-01-01")],
        chart="line")
    add("R07", "retail", "retail_price_distribution", "visualization",
        "For Japan positive sales (Quantity>0, 0<UnitPrice<=50, InvoiceNo not starting with C), "
        "draw a histogram of all nonmissing UnitPrice values using 20 equal-width bins. "
        "Label price in GBP per unit and frequency as transaction lines; no sampling.",
        operation="raw", column="UnitPrice", groups=[],
        filters=positive + [("Country", "eq", "Japan"), ("UnitPrice", "le", 50)],
        chart="histogram", ordered=False)
    add("R08", "retail", "retail_price_quantity", "visualization",
        "For Germany positive sales in April 2011 (Quantity>0, UnitPrice>0, InvoiceNo not "
        "starting with C), scatter-plot Quantity on x and UnitPrice on y, using every paired "
        "nonmissing line. Parse InvoiceDate; select 2011-04-01 inclusive to 2011-05-01 exclusive. "
        "Label units and GBP per unit. Describe any relationship as association.",
        operation="raw", column="Quantity", other_column="UnitPrice", groups=[],
        dates=["InvoiceDate"], filters=positive + [("Country", "eq", "Germany"),
            ("InvoiceDate", "ge", "2011-04-01"), ("InvoiceDate", "lt", "2011-05-01")],
        chart="scatter", ordered=False)
    add("R09", "retail", "retail_cancellations", "exploration",
        "Audit cancelled transaction lines (InvoiceNo starts with C): investigate their "
        "UnitPrice values, including nonpositive prices, and record counts across Country. "
        "Give up to three traceable findings with valid counts and explicit denominators. "
        "UnitPrice is GBP per unit; do not substitute Quantity totals or revenue ranking. "
        "Distinguish transaction records from distinct invoices and disclose exclusions.")
    add("R10", "retail", "retail_prices", "exploration",
        "Investigate unusual UnitPrice patterns in this Retail file, including nonpositive "
        "prices and extreme positive prices. Give up to three useful findings with computed "
        "evidence and counts. Do not assume an unusual line is a data error or a distinct product.")

    add("B01", "bike", "bike_component_totals", "explicit",
        "Sum casual rentals by workingday (0/1), include valid casual observation counts, "
        "sort workingday ascending. Treat these as totals over observed hours, not daily means.",
        operation="sum", column="casual", groups=["workingday"])
    add("B02", "bike", "bike_component_share", "explicit",
        "For each weathersit, compute sum(registered)/sum(cnt), using rows where both values "
        "are present; return a fraction, not a percentage or mean of hourly fractions. "
        "Include paired counts and sort weathersit ascending. No causal interpretation.",
        operation="ratio", column="registered", other_column="cnt", groups=["weathersit"])
    add("B03", "bike", "bike_weather_summary", "explicit",
        "Compute the mean normalized humidity hum by season, include valid hum counts and "
        "sort season ascending. Keep hum on the supplied 0..1 scale; summarize observed hours.",
        operation="mean", column="hum", groups=["season"])
    add("B04", "bike", "bike_component_share", "explicit",
        "By season, compute sum(casual)/sum(cnt) over complete casual/cnt pairs, "
        "including paired valid counts. Drop missing season; sort season ascending. "
        "Return fractions, not percentages or means of hourly fractions; a zero "
        "denominator gives an undefined value. Describe the casual share of rentals "
        "over observed hours, not temporal record coverage.",
        operation="ratio", column="casual", other_column="cnt", groups=["season"])
    add("B05", "bike", "bike_component_totals", "visualization",
        "Bar-chart total registered rentals by workingday (0 then 1), include valid counts. "
        "Label y total registered rentals across observed hours, not mean rentals.",
        operation="sum", column="registered", groups=["workingday"], chart="bar")
    add("B06", "bike", "bike_weather_summary", "visualization",
        "For 2012, line-chart mean normalized temp by mnth, with valid temp counts, months "
        "ascending. Parse dteday and select 2012-01-01 inclusive to 2013-01-01 exclusive. "
        "Keep the supplied temperature/41 scale and label it explicitly, not degrees Celsius.",
        operation="mean", column="temp", groups=["mnth"], dates=["dteday"],
        filters=[("dteday", "ge", "2012-01-01"), ("dteday", "lt", "2013-01-01")], chart="line")
    add("B07", "bike", "bike_inclement_distribution", "visualization",
        "For yr=0 and weathersit=3, histogram all nonmissing cnt values with 20 equal-width "
        "bins; no sampling. Label x rentals per observed hour and y observed hourly records.",
        operation="raw", column="cnt", groups=[],
        filters=[("yr", "eq", 0), ("weathersit", "eq", 3)], chart="histogram", ordered=False)
    add("B08", "bike", "bike_component_share", "visualization",
        "For yr=1 and hr=12, scatter-plot all paired nonmissing casual (x) and registered "
        "(y) rental counts. Label each axis rentals per observed hour for its user type. "
        "Use every complete pair, preserving duplicate observations; do not sample "
        "or normalize by total cnt. Describe co-variation, without causal claims.",
        operation="raw", column="casual", other_column="registered", groups=[],
        filters=[("yr", "eq", 1), ("hr", "eq", 12)], chart="scatter", ordered=False)
    add("B09", "bike", "bike_component_totals", "exploration",
        "Explore how casual and registered users contribute to observed bike demand across "
        "workingday categories. Give up to three evidence-grounded findings, distinguish sums "
        "from means and unequal observation counts, and avoid causal claims.")
    add("B10", "bike", "bike_component_share", "exploration",
        "Explore casual versus registered contributions to bike rentals across yr and "
        "season. Give up to three traceable findings about component totals or shares, "
        "with paired observation counts and explicit denominators. Distinguish ratios "
        "of totals from means of hourly fractions; do not replace this with total-demand "
        "means or a temporal record-coverage analysis. Avoid causal claims.")

    add("A01", "adult", "adult_capital_loss", "explicit",
        "Sum capital-loss by sex, including valid capital-loss observation counts. "
        "Keep zero losses, drop missing sex or capital-loss, and sort sex ascending. "
        "Use unweighted observed capital-loss amounts, not loss-bearing record counts, "
        "capital-gain or fnlwgt. Describe this sample without population estimates.",
        operation="sum", column="capital-loss", groups=["sex"])
    add("A02", "adult", "adult_capital_loss", "explicit",
        "For each workclass, compute sum(capital-loss)/sum(capital-gain), unweighted, "
        "over complete loss/gain pairs. Include paired valid counts, including pairs "
        "with zero values. Treat ?/blank workclass as missing and drop those group keys; "
        "sort workclass ascending. A zero denominator gives an undefined value. "
        "This is a ratio of observed capital amounts, not a fraction of people; do not "
        "use fnlwgt or average person-level ratios.",
        operation="ratio", column="capital-loss", other_column="capital-gain", groups=["workclass"])
    add("A03", "adult", "adult_capital_loss", "explicit",
        "For sample records with capital-loss>0, count records by marital-status and sex, "
        "unweighted. Drop missing group keys (? and blanks); sort marital-status then sex "
        "ascending and return observed combinations only. Count loss-bearing records, "
        "without deduplicating people or summing loss amounts.",
        operation="rows", groups=["marital-status", "sex"], filters=[("capital-loss", "gt", 0)])
    add("A04", "adult", "adult_education_mapping", "explicit",
        "Audit the education-label/code mapping: count unweighted sample records by "
        "education and education-num, dropping missing group keys (? and blanks). "
        "Sort education ascending then education-num numerically ascending; return "
        "observed pairs only. Preserve education labels and treat education-num as "
        "an ordinal code, not years of schooling. Do not deduplicate repeated records.",
        operation="rows", groups=["education", "education-num"])
    add("A05", "adult", "adult_capital_loss", "visualization",
        "For sample records with capital-loss>0, bar-chart unweighted record counts by "
        "workclass, sorted workclass ascending. Drop missing workclass (? and blanks); "
        "include contributing counts. Label the y axis loss-bearing sample records. "
        "Do not plot loss amounts, capital-gain means or population estimates.",
        operation="rows", groups=["workclass"], filters=[("capital-loss", "gt", 0)], chart="bar")
    add("A06", "adult", "adult_capital_loss", "visualization",
        "For records with age>=60, line-chart unweighted mean capital-loss by single-year "
        "age, sorted age ascending, with valid capital-loss counts. Keep zero losses; "
        "drop missing age or capital-loss. Label age in years and mean observed capital-loss "
        "amount. Do not bin ages, use fnlwgt, substitute capital-gain or infer population effects.",
        operation="mean", column="capital-loss", groups=["age"],
        filters=[("age", "ge", 60)], chart="line")
    add("A07", "adult", "adult_oldest_age_distribution", "visualization",
        "For age>=80, histogram every nonmissing age using 10 equal-width bins; no sampling. "
        "Label age in years and frequency as sample records. Use unweighted counts.",
        operation="raw", column="age", groups=[], filters=[("age", "ge", 80)],
        chart="histogram", ordered=False)
    add("A08", "adult", "adult_capital_loss", "visualization",
        "For records with capital-loss>0, scatter-plot all paired nonmissing fnlwgt (x) "
        "and capital-loss (y), unweighted and without sampling. Label x supplied final "
        "survey weight and y capital-loss amount. Preserve duplicate observations. "
        "Describe association among loss-bearing sample records, not population or "
        "causal effects; fnlwgt is not income or a monetary amount.",
        operation="raw", column="fnlwgt", other_column="capital-loss", groups=[],
        filters=[("capital-loss", "gt", 0)], chart="scatter", ordered=False)
    add("A09", "adult", "adult_education_mapping", "exploration",
        "Investigate the correspondence between education labels and education-num "
        "codes. Give up to three useful findings grounded in counts of observed pairs "
        "and missing entries. Check whether each observed label maps to one or multiple "
        "codes and vice versa; describe the actually computed result, without assuming "
        "the mapping is inconsistent. Codes are ordinal, not years of schooling. "
        "Do not substitute income, age or working-hours comparisons.")
    add("A10", "adult", "adult_capital_loss", "exploration",
        "Investigate capital-loss occurrence in this Adult sample and its joint "
        "occurrence with positive capital-gain. Give up to three traceable findings "
        "with unweighted counts and explicit denominators, optionally comparing "
        "workclass or sex. Distinguish zero values from missing values, loss-bearing "
        "record counts from loss amounts, and disclose missing-key exclusions. "
        "Do not substitute mean capital-gain comparisons or make population or causal claims.")
    # Conservative connected families: exploratory tasks bridge related test templates.
    # Preserve those dependencies when resampling, even though all are on the test side.
    for task in tasks:
        if task["dataset"] == "retail" and task["family"] != "retail_record_activity":
            task["family"] = "retail_price_cancellation_audit"
        if task["family"] in {"bike_component_totals", "bike_component_share"}:
            task["family"] = "bike_component_composition"
    return tasks, specs


VARIANTS = [
    ("R02", "numeric_strings", "UnitPrice"),
    ("R02", "missing_values", "UnitPrice"),
    ("R06", "mixed_dates", "InvoiceDate"),
    ("R03", "missing_values", "Country"),
    ("B01", "numeric_strings", "casual"),
    ("B02", "missing_values", "registered"),
    ("B04", "missing_values", "season"),
    ("B06", "mixed_dates", "dteday"),
    ("A01", "numeric_strings", "capital-loss"),
    ("A02", "numeric_strings", "capital-gain"),
    ("A04", "missing_values", "education-num"),
    ("A03", "missing_values", "sex"),
]
