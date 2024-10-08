import pytest

from gpw_scraper.beautifulsoup import BeautifulSoup

TABLE_1 = """
<table><tbody><tr><td></td><td colspan="11"><p>KOMISJA NADZORU FINANSOWEGO</p></td><td></td></tr><tr><td></td><td><span face="Times New Roman"><p></p></span></td><td><span face="Times New Roman"></span></td><td colspan="4"><p>Raport bieżący nr</p></td><td><p>45</p></td><td><p>/</p></td><td><p>2024</p></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="2"><p>Data sporządzenia:</p></td><td><p>2024-10-08</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="3"><p>Skrócona nazwa emitenta</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="11"><p>KETY</p></td><td></td></tr><tr><td></td><td colspan="2"><p>Temat</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="11"><p>Rezygnacja członka Rady Nadzorczej</p></td><td></td></tr><tr><td></td><td colspan="4"><p>Podstawa prawna</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="11"><p>Art. 56 ust. 1 pkt 2 Ustawy o ofercie - informacje bieżące i okresowe</p></td><td></td></tr><tr><td></td><td colspan="3"><p>Treść raportu:</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="11"><p>Zarząd Grupy Kęty S.A. (dalej: Spółka lub Emitent) informuje, że w dniu dzisiejszym Spółka otrzymała rezygnację Pana Przemysława Gardockiego z pełnienia funkcji członka Rady Nadzorczej Emitenta.</p><p>Pan Przemysław Gardocki nie podał przyczyn rezygnacji.</p></td><td></td></tr></tbody></table>
"""

TABLE_2 = """
<table><tbody><tr><td></td><td colspan="10"><p>POLISH FINANCIAL SUPERVISION AUTHORITY</p></td><td></td></tr><tr><td></td><td><span face="Times New Roman"><p></p></span></td><td><span face="Times New Roman"></span></td><td><span face="Times New Roman"></span></td><td colspan="2"><p>UNI - EN REPORT No</p></td><td><p>27</p></td><td><p>/</p></td><td><p>2024</p></td><td></td><td><span face="Times New Roman"></span></td><td></td></tr><tr><td></td><td colspan="2"><p>Date of issue:</p></td><td><p>2024-10-08</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="4"><p>Short name of the issuer</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="10"><p>OVOSTAR UNION PCL</p></td><td></td></tr><tr><td></td><td><p>Subject</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="10"><p>INFORMATION ON POSTPONING COMPLETION OF THE ADMINISTRATIVE PROCEEDINGS BY THE POLISH FINANCIAL SUPERVISION AUTHORITY</p></td><td></td></tr><tr><td></td><td colspan="5"><p>Official market - legal basis</p></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="10"><p>art. 17. 1 MAR.</p></td><td></td></tr><tr><td></td><td colspan="6"><p>Unofficial market - legal basis</p></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="3"><p>Contents of the report:</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="10"><p>Please see attached</p></td><td></td></tr><tr><td></td><td><p>Annexes</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="4"><p>File</p></td><td colspan="6"><p>Description</p></td><td></td></tr></tbody></table>
"""

TABLE_3 = """
<table><tbody><tr><td></td><td colspan="10"><p>KOMISJA NADZORU FINANSOWEGO</p></td><td></td></tr><tr><td></td><td><span face="Times New Roman"><p></p></span></td><td><span face="Times New Roman"></span></td><td><span face="Times New Roman"></span></td><td colspan="2"><p>Raport bieżący nr</p></td><td><p>29</p></td><td><p>/</p></td><td><p>2024</p></td><td></td><td><span face="Times New Roman"></span></td><td></td></tr><tr><td></td><td colspan="2"><p>Data sporządzenia:</p></td><td><p>2024-10-07</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="4"><p>Skrócona nazwa emitenta</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="10"><p>LW BOGDANKA S.A.</p></td><td></td></tr><tr><td></td><td><p>Temat</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="10"><p>Odpowiedzi na pytania akcjonariusza zadane w trybie art. 428 §6 KSH</p></td><td></td></tr><tr><td></td><td colspan="4"><p>Podstawa prawna</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><tr><td></td><td colspan="10"><p>Art. 56 ust. 1 pkt 2 Ustawy o ofercie - informacje bieżące i okresowe</p></td><td></td></tr><tr><td></td><td><p>Załączniki</p></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr><div></div></tbody></table>
"""


@pytest.mark.parametrize(
    ["content", "expected"],
    [
        [
            TABLE_1,
            "Zarząd Grupy Kęty S.A. (dalej: Spółka lub Emitent) informuje, że w dniu dzisiejszym Spółka otrzymała rezygnację Pana Przemysława Gardockiego z pełnienia funkcji członka Rady Nadzorczej Emitenta.Pan Przemysław Gardocki nie podał przyczyn rezygnacji.",
        ],
        [TABLE_2, "Please see attached"],
        [TABLE_3, None],
    ],
    ids=["pl_content", "eng_content", "none"],
)
def test_pap_espi_get_content(content: str, expected: str | None):
    soup = BeautifulSoup(content, features="html.parser")
    result = soup.pap_espi_get_content()
    assert result == expected
