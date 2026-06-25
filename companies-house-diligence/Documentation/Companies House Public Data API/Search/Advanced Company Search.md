# Advanced search for a company

Advanced search for a company

## Request

```
GET https://api.company-information.service.gov.uk/advanced-search/companies
```

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_name_includes | string | The company name includes advanced search filter |  |
| company_name_excludes | string | The company name excludes advanced search filter |  |
| company_status | list | The company status advanced search filter. To search using multiple values, use a comma delimited list or multiple of the same key i.e. company_status=xxx&company_status=yyy |  |
| company_subtype | string | The company subtype advanced search filter. To search using multiple values, use a comma delimited list or multiple of the same key i.e. company_subtype=xxx&company_subtype=yyy |  |
| company_type | list | The company type advanced search filter. To search using multiple values, use a comma delimited list or multiple of the same key i.e. company_type=xxx&company_type=yyy |  |
| dissolved_from | date | The dissolved from date advanced search filter |  |
| dissolved_to | date | The dissolved to date advanced search filter |  |
| incorporated_from | date | The incorporated from date advanced search filter |  |
| incorporated_to | date | The incorporated to date advanced search filter |  |
| location | string | The location advanced search filter |  |
| sic_codes | list | The SIC codes advanced search filter. To search using multiple values, use a comma delimited list or multiple of the same key i.e. sic_codes=xxx&sic_codes=yyy |  |
| size | string | The maximum number of results matching the search term(s) to return with a range of 1 to 5000 |  |
| start_index | string | The point at which results will start from i.e show search results from result 20 (used for paging) |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK A list of companies | [A list of companies](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/a-list-of-companies?v=latest) |
| 400 | Bad Request Bad request |  |
| 404 | Not Found No companies found |  |
