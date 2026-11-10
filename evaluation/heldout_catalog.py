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
        "For InvoiceNo starting with C, sum signed Quantity by Country; retain negative signs. "
        "Include valid Quantity counts, exclude missing Country, sort Country ascending.",
        operation="sum", column="Quantity", groups=["Country"], filters=cancelled)
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
        "Explore cancelled lines (InvoiceNo starts with C): their concentration across Country "
        "and StockCode and signed Quantity totals. Give up to three traceable findings. "
        "Distinguish transaction records from distinct invoices, and disclose exclusions.")
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
    add("B04", "bike", "bike_record_coverage", "explicit",
        "Count observed hourly records by yr and season, dropping missing group keys. "
        "Sort yr then season ascending. Report record counts, not rental totals or day counts.",
        operation="rows", groups=["yr", "season"])
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
    add("B08", "bike", "bike_temperature_pair", "visualization",
        "For yr=1 and hr=12, scatter-plot all paired nonmissing temp (x) and atemp (y). "
        "Use normalized scales: temperature/41 and feels-like temperature/50. "
        "Do not sample or describe either axis as raw Celsius.",
        operation="raw", column="temp", other_column="atemp", groups=[],
        filters=[("yr", "eq", 1), ("hr", "eq", 12)], chart="scatter", ordered=False)
    add("B09", "bike", "bike_component_totals", "exploration",
        "Explore how casual and registered users contribute to observed bike demand across "
        "workingday categories. Give up to three evidence-grounded findings, distinguish sums "
        "from means and unequal observation counts, and avoid causal claims.")
    add("B10", "bike", "bike_record_coverage", "exploration",
        "Inspect coverage of observed hourly records across yr and season. Give up to three "
        "findings useful before comparing rental totals. Support statements with counts; do "
        "not infer missing hours or their causes without computing the relevant coverage.")

    add("A01", "adult", "adult_age_income", "explicit",
        "Compute unweighted mean age by income, including valid age counts. "
        "Drop missing income, sort income ascending. Describe this sample only.",
        operation="mean", column="age", groups=["income"])
    add("A02", "adult", "adult_capital_workclass", "explicit",
        "Sum capital-gain by workclass with valid capital-gain counts, unweighted. "
        "Treat ?/blank workclass as missing and drop those group keys; sort workclass ascending. "
        "Do not treat fnlwgt as income or a multiplier.",
        operation="sum", column="capital-gain", groups=["workclass"])
    add("A03", "adult", "adult_household_composition", "explicit",
        "Count sample records by relationship and sex, unweighted. Drop missing group keys; "
        "sort relationship then sex ascending. Count records, without deduplicating people.",
        operation="rows", groups=["relationship", "sex"])
    add("A04", "adult", "adult_occupation_missingness", "explicit",
        "Count missing occupation entries by income (? and blanks are missing). "
        "Also include total sample records in each income group as valid_count. "
        "Drop missing income, keep rows missing occupation, sort income ascending; unweighted.",
        operation="missing", column="occupation", groups=["income"])
    add("A05", "adult", "adult_capital_income", "visualization",
        "Bar-chart total capital-loss by income, unweighted, with valid capital-loss counts; "
        "sort income ascending. Label totals rather than average losses; describe this sample.",
        operation="sum", column="capital-loss", groups=["income"], chart="bar")
    add("A06", "adult", "adult_older_work", "visualization",
        "For records with age>=60, draw a line chart of unweighted mean hours-per-week by "
        "single-year age, sorted age ascending. Include valid hours counts and label weekly "
        "working hours. Do not bin ages or infer a population retirement effect.",
        operation="mean", column="hours-per-week", groups=["age"],
        filters=[("age", "ge", 60)], chart="line")
    add("A07", "adult", "adult_oldest_age_distribution", "visualization",
        "For age>=80, histogram every nonmissing age using 10 equal-width bins; no sampling. "
        "Label age in years and frequency as sample records. Use unweighted counts.",
        operation="raw", column="age", groups=[], filters=[("age", "ge", 80)],
        chart="histogram", ordered=False)
    add("A08", "adult", "adult_oldest_education", "visualization",
        "For age>=80, scatter-plot all paired nonmissing age (x) and education-num (y), "
        "unweighted, without sampling. Label age in years and education-num as an ordinal code. "
        "Describe associations within this sample only.",
        operation="raw", column="age", other_column="education-num", groups=[],
        filters=[("age", "ge", 80)], chart="scatter", ordered=False)
    add("A09", "adult", "adult_capital_income", "exploration",
        "Explore capital-gain and capital-loss across income categories in this sample. "
        "Give up to three useful findings with computed evidence, distinguish totals and means, "
        "and disclose zero values and sample counts. Use unweighted summaries, no causal claims.")
    add("A10", "adult", "adult_older_work", "exploration",
        "For age>=60, explore weekly working hours across sex and workclass categories. "
        "Give up to three traceable, useful findings with valid counts and missing-group "
        "handling. Describe unweighted observed records without population or causal claims.")
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
    ("A01", "numeric_strings", "age"),
    ("A02", "numeric_strings", "capital-gain"),
    ("A04", "missing_values", "occupation"),
    ("A03", "missing_values", "sex"),
]
