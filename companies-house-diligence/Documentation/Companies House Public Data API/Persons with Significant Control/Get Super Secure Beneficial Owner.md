# Get the super secure beneficial owner

Get details of a super secure beneficial owner

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control/super-secure-beneficial-owner/{super_secure_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the super secure beneficial owner details being requested. | Required |
| super_secure_id | string | The id of the super secure beneficial owner details being requested. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK SuperSecureBO resource returned | [superSecureBeneficialOwner](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/supersecurebeneficialowner?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
