from earnings_signal.dzh_client import DzhClient


def test_paged_get_fetches_all_pages_and_deduplicates():
    def transport(url, headers, timeout):
        assert "Hydata-Apikey" in headers
        if "pno=1" in url:
            return {"reccount": 3, "rows": [{"NewsId": 1}, {"NewsId": 2}]}
        return {"reccount": 3, "rows": [{"NewsId": 2}, {"NewsId": 3}]}

    client = DzhClient(api_key="test", transport=transport)
    result = client.paged_get("/News/stock", {"stock": "300750"}, page_size=2)

    assert result.reccount == 3
    assert result.pages_fetched == 2
    assert result.duplicate_rows == 1
    assert [row["NewsId"] for row in result.rows] == [1, 2, 3]

