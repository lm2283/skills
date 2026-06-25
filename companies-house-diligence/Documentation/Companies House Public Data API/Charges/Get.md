Individual charge information for company.

## Request

```
GET https://api.company-information.service.gov.uk/company/{company_number}/charges/{charge_id}
```

## Authorisation

This request requires the use of one of following authorisation methods: `API key` .

## Response

The following HTTP status codes may be returned, optionally with a response resource.

| Status code | Description | Resource |
| --- | --- | --- |
| 200 | OK Resource returned | [chargeDetails](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/chargedetails?v=latest) |
| 401 | Unauthorized Unauthorised |  |
| 404 | Not Found Resource not found |  |
