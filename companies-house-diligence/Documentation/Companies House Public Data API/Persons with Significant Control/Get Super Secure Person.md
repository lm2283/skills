# Get the super secure person with significant control

Get details of a super secure person with significant control

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control/super-secure/{super_secure_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the super secure person with significant control details being requested. | Required |
| super_secure_id | string | The id of the super secure person with significant control details being requested. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK SuperSecurePSC resource returned | [superSecure](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/supersecure?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
