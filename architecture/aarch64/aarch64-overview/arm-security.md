## what do we mean by security

asset: things that we want to protect

confidentiality: "who can see, access, or use an asset"

integrity: "the accuracy and completeness" of an asset

authenticity: for example, a software update should be signed by the publisher, otherwise the device should reject this update

availability: authorizes users can use the assets in the way that they are intended to be used(counterpart: Denial-of-service attack)

## Attacking a system

threat: a combination of an attacker, an exploit, and a set of assets to be attacked

types of attack: SW attack/basic HW attack/advanced HW attack

different attackers: third parties/users of the devices(for copyright or something like that)

threat models!

## Different security solutions

security requirements in value terms: "Attack A on asset B should take at least Y days and Z dollars"

we should consider these aspects:

* value of asset: different security aspects of an asset may be valued differently
* cost of defense
* practicality and usability

abstraction of security(increasing): OS->Hypervisor->TrustZone TEE(Trusted Domain)->SecurCore SEE(Secure Domain)

