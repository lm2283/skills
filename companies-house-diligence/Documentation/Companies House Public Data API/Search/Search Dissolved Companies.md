# Search for a dissolved company

Search for a dissolved company

## Request

```
GET https://api.company-information.service.gov.uk/dissolved-search/companies
```

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| q | string | The company name being searched for | Required |
| search_type | string | Determines type of search. Options are alphabetical, best-match, previous-name-dissolved | Required |
| search_above | string | The ordered_alpha_key_with_id used for alphabetical paging |  |
| search_below | string | The ordered_alpha_key_with_id used for alphabetical paging |  |
| size | string | The maximum number of results matching the search term(s) to return with a range of 1 to 100 |  |
| start_index | string | Used in best-match and previous-name-dissolved search-type |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK A list of dissolved companies | [List of dissolved companies](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/list-of-dissolved-companies?v=latest) |
| 404 | Not Found No companies found |  |
| 422 | Invalid size parameter, size must be greater than zero and not greater than 100 |  |
