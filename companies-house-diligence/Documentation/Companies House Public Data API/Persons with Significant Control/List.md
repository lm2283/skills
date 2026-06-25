# List the company persons with significant control

List of all persons with significant control (not statements)

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the persons with significant control list being requested. | Required |

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| items_per_page | string | The number of persons with significant control to return per page. | Required |
| start_index | string | The offset into the entire result set that this page starts. | Required |
| register_view | string | Display register specific information. If register is held at Companies House and register_view is set to true, only PSCs which are active or were terminated during election period are shown. Accepted values are: - `true` - `false` Defaults to false. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK readCompanyProfile | [list](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/list?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
