# Get the corporate entity beneficial owner notification

Get details of the corporate entity beneficial owner notification

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/persons-with-significant-control/corporate-entity-beneficial-owner/{notification_id}
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the corporate entity beneficial owner details being requested. | Required |
| notification_id | string | The notification id of the corporate entity beneficial owner notification being requested. | Required |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK CorporateEntityBO resource returned | [corporateEntityBeneficialOwner](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/corporateentitybeneficialowner?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
