# Get the corporate entity with significant control notification

Get details of a corporate entity with significant control notification

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control/corporate-entity/{notification_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the corporate entity with significant control details being requested. | Required |
| notification_id | string | The notification id of the corporate entity with significant control notification being requested. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK CorporateEntityPSC resource returned | [corporateEntity](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/corporateentity?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
