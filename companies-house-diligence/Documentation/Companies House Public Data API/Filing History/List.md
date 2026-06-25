# filingHistoryList resource

Get the filing history list of a company

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/filing-history
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number that the filing history is required for. | Required |

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| category | string | One or more comma-separated categories to filter by (inclusive). |  |
| items_per_page | integer | The number of filing history items to return per page. |  |
| start_index | integer | The index into the entire result set that this result page starts. |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Filing history items resource returned | [filingHistoryList](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/filinghistorylist?v=latest) |
| 401 | Unauthorized Unauthorised | [error](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/error?v=latest) |
| 404 | Not Found Filing history not available for this company |  |
