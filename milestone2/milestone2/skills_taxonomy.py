"""
skills_taxonomy.py
Canonical skill list + alias map, shared by extractor.py (resumes) and
job_parser.py (job descriptions) so both sides of the match use the exact
same vocabulary. Extend SKILL_TAXONOMY as your domain needs grow -- no
other code needs to change when you add a skill here.
"""

import re
from typing import List

# canonical name -> list of text variants that should count as a match
SKILL_TAXONOMY = {
    "Python": ["python"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "Go": ["golang"],
    "SQL": ["sql"],
    "HTML": ["html"],
    "CSS": ["css"],
    "Machine Learning": ["machine learning", " ml "],
    "Deep Learning": ["deep learning"],
    "Artificial Intelligence": ["artificial intelligence"],
    "Natural Language Processing": ["natural language processing", "nlp"],
    "Computer Vision": ["computer vision"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Keras": ["keras"],
    "Scikit-learn": ["scikit-learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Matplotlib": ["matplotlib"],
    "Seaborn": ["seaborn"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Exploratory Data Analysis": ["exploratory data analysis", "eda"],
    "Data Cleaning": ["data cleaning", "data preprocessing", "data preparation", "data wrangling"],
    "Regression": ["regression"],
    "Classification": ["classification"],
    "Predictive Modeling": ["predictive modeling", "predictive modelling"],
    "Data Science": ["data science"],
    "Data Engineering": ["data engineering"],
    "Big Data": ["big data"],
    "Apache Spark": ["apache spark", "pyspark", "spark"],
    "Hadoop": ["hadoop"],
    "AWS": ["aws", "amazon web services"],
    "AWS SageMaker": ["sagemaker", "aws sagemaker"],
    "Azure": ["azure", "microsoft azure"],
    "Google Cloud (GCP)": ["gcp", "google cloud"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "CI/CD": ["ci/cd", "continuous integration"],
    "Git": ["git"],
    "GitHub": ["github"],
    "Linux": ["linux"],
    "Jupyter Notebook": ["jupyter notebook", "jupyter"],
    "VS Code": ["vs code", "visual studio code"],
    "React": ["react.js", "reactjs", "react"],
    "Node.js": ["node.js", "nodejs"],
    "Angular": ["angular"],
    "Vue.js": ["vue.js", "vuejs"],
    "Django": ["django"],
    "Flask": ["flask"],
    "REST APIs": ["rest api", "restful api", "rest apis"],
    "GraphQL": ["graphql"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "SQLite": ["sqlite"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Excel": ["excel", "ms excel"],
    "Project Management": ["project management"],
    "Agile/Scrum": ["agile", "scrum"],
    "Communication": ["communication skills"],
    "Leadership": ["leadership"],
    "HuggingFace Transformers": ["huggingface", "transformers library"],
    "Statistics": ["statistics", "statistical analysis"],
    "A/B Testing": ["a/b testing", "ab testing"],
    "ETL": ["etl pipeline", "etl"],
    "Data Visualization": ["data visualization"],
}

_ALIAS_PATTERNS = None


def _build_patterns():
    global _ALIAS_PATTERNS
    if _ALIAS_PATTERNS is not None:
        return _ALIAS_PATTERNS
    patterns = []
    for canonical, aliases in SKILL_TAXONOMY.items():
        for alias in aliases:
            alias = alias.strip()
            if not alias:
                continue
            escaped = re.escape(alias)
            # word-boundary-ish match so "R" doesn't match inside "Robert",
            # and "Go" doesn't match inside "Google" (still lets "C++" match)
            pattern = re.compile(rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])", re.IGNORECASE)
            patterns.append((canonical, pattern))
    _ALIAS_PATTERNS = patterns
    return patterns


def extract_skills_from_text(text: str) -> List[str]:
    """Scan free text (resume or job description) and return the sorted
    list of canonical skill names detected."""
    if not text:
        return []
    found = set()
    for canonical, pattern in _build_patterns():
        if pattern.search(text):
            found.add(canonical)
    return sorted(found)