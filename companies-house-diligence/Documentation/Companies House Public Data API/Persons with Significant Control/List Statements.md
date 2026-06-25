# List the company persons with significant control statements

List of all persons with significant control statements

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control-statements
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the persons with significant control statements list being requested. | Required |

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| items_per_page | integer | The id of the legal person with significant control details being requested. | Required |
| start_index | integer | The offset into the entire result set that this page starts. | Required |
| register_view | query | Display register specific information. If register is held at Companies House and register_view is set to true, only statements which are active or were withdrawn during election period are shown. Accepted values are: - `true` - `false` Defaults to false. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK CompanyPSCStatements resource returned | [statementList](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/statementlist?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
