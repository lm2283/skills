# Company Officers

List of all company officers

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/officers
```

## Path parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| company_number | string | The company number of the officer list being requested. | Required |

## Query parameters

| Parameter name | Value | Description | Additional |
| --- | --- | --- | --- |
| items_per_page | integer | The number of officers to return per page. |  |
| register_type | string | The register_type determines which officer type is returned for the registers view.The register_type field will only work if registers_view is set to true Possible values are: `directors` `secretaries` `llp_members` |  |
| register_view | string | Display register specific information. If given register is held at Companies House, registers_view set to true and correct register_type specified, only active officers will be returned. Defaults to false Possible values are: `true` `false` |  |
| start_index | integer | The offset into the entire result set that this page starts. |  |
| order_by | string | The field by which to order the result set. Possible values are: `appointed_on` `resigned_on` `surname` |  |

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK List the company officers | [officerList](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/officerlist?v=latest) |
| 400 | Bad Request Bad request | [error](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/error?v=latest) |
| 401 | Unauthorized Unauthorised |  |

### Headers returned

| Name | Type | Description |
| --- | --- | --- |
| ETag | string | The ETag of the resource. |
