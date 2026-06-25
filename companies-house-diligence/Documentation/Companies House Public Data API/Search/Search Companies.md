# Search companies

Search company information

## Request

```
GET https://api.company-information.service.gov.uk/search/companies
```

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| q | string | The term being searched for. | Required |
| items_per_page | integer | The number of search results to return per page. |  |
| start_index | integer | The index of the first result item to return. |  |
| restrictions | string | Enumerable options to restrict search results. Space separate multiple restriction options to combine functionality. For a "company name availability" search use "active-companies legally-equivalent-company-name" together. |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Search company | [CompanySearch](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companysearch?v=latest) |
| 401 | Unauthorized Not authorised |  |
