"""python -m cookie_cats : run the analysis, write results/metrics.json, figures and README."""
from .analysis import analyse, load, write_metrics
from .figures import build_all
from .report import render


def main() -> None:
    df = load()
    metrics, boots = analyse(df)
    print("metrics ->", write_metrics(metrics))
    for p in build_all(df, metrics, boots):
        print("figure  ->", p)
    for p in render(metrics):
        print("report  ->", p)


if __name__ == "__main__":
    main()
