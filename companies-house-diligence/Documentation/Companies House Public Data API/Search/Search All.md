# Search All

Search companies, officers and disqualified officers

## Request

```
GET https://api.company-information.service.gov.uk/search
```

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| q | string | The term being searched for. | Required |
| items_per_page | integer | The number of search results to return per page. |  |
| start_index | integer | The index of the first result item to return. |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Search all | [Search](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/search?v=latest) |
| 401 | Unauthorized Not authorised |  |
