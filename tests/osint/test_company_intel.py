from core.osint.company_intel import CompanyIntelligence


def test_company_intent_detection():
    assert CompanyIntelligence.is_company_intent("analysiere firma Siemens AG")
    assert CompanyIntelligence.is_company_intent("Siemens AG")
    assert not CompanyIntelligence.is_company_intent("what is photosynthesis")
    assert not CompanyIntelligence.is_company_intent("Who is Angela Merkel")
    assert not CompanyIntelligence.is_company_intent("Explain Newton laws")


def test_extract_company_name():
    name = CompanyIntelligence.extract_company_name(
        "Analysiere die Firma Siemens AG Vorstand und Struktur"
    )
    assert name == "Siemens AG"

    with_hints = CompanyIntelligence.extract_company_name(
        "analyze company Siemens AG country:DE region:de-de lang:de"
    )
    assert with_hints == "Siemens AG"


def test_analyze_company_with_mocked_search(monkeypatch):
    def fake_search(query, max_results, region, safesearch, ranking_profile):
        if "CEO OR CFO" in query:
            return [
                {
                    "title": "Siemens names new CEO",
                    "url": "https://www.siemens.com/press/ceo",
                    "snippet": "CEO Jane Doe will lead Siemens AG from 2026.",
                }
            ]
        if "subsidiaries OR holding" in query:
            return [
                {
                    "title": "Siemens AG – Subsidiaries and holdings",
                    "url": "https://www.siemens.com/investor/structure",
                    "snippet": "The Siemens group includes several subsidiaries and holding entities.",
                }
            ]
        if "lawsuit OR fine" in query:
            return [
                {
                    "title": "Compliance update",
                    "url": "https://www.reuters.com/world/europe/siemens-compliance-update",
                    "snippet": "No major fine reported in the latest compliance update.",
                }
            ]
        return [
            {
                "title": "Siemens AG official website",
                "url": "https://www.siemens.com/",
                "snippet": "Official company profile for Siemens AG.",
            }
        ]

    monkeypatch.setattr("core.osint.company_intel.search_with_fallback", fake_search)

    intel = CompanyIntelligence(config={"search": {"region": "de-de"}, "osint": {"safesearch": "strict"}})
    monkeypatch.setattr(
        intel.domain_intelligence,
        "analyze_domain",
        lambda domain: {"domain": domain, "valid": True, "ips": ["1.1.1.1"]},
    )

    result = intel.analyze_company("Siemens AG")

    assert result["company_name"] == "Siemens AG"
    assert result["official_domain"] == "siemens.com"
    assert result["source_count"] >= 3
    assert result["leadership_signals"]
    assert result["structure_signals"]

    report = intel.format_report(result)
    assert "Company Intelligence" in report
    assert "Likely Official Domain" in report
