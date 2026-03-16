import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { checkAgreement, acceptAgreement } from "../api";

const LICENSE_TEXT = `TokReducer
Intellectual Property, Licensing & Commercial Protection Agreement
Version 1.0 -- Effective March 16, 2026
Proprietary and Confidential

Important notice
This document contains the intellectual property ownership declaration, proprietary software license, trade secret protections, and commercial terms governing TokReducer. Unauthorized copying, distribution, reverse engineering, or use without a valid commercial license is strictly prohibited and may result in civil and criminal liability.

1. Intellectual Property Ownership

1.1 Ownership declaration
TokReducer -- including its name, compression protocol specification, syntax, operator definitions, macro system, software libraries (Python and Rust), documentation, test suites, and all associated intellectual property -- is the exclusive property of its creator (the "Owner"). All rights are reserved globally.

1.2 What is protected
- The TokReducer trademark and brand identity
- The TokReducer 1.0 compression protocol specification and syntax
- All operator definitions, macro systems, and compression algorithms
- The Python library source code and Rust core library
- The system prompt injection methodology and output-completeness enforcement mechanism
- All unit tests, benchmarks, and performance measurement methodologies
- All documentation, guides, and educational materials
- The TokReducer website, domain, and all web assets
- Trade secrets including compression heuristics and provider-specific optimizations

Copyright (c) 2026 TokReducer -- All Rights Reserved.
This software and protocol are protected under international copyright law. Unauthorized reproduction or distribution may result in severe civil and criminal penalties and will be prosecuted to the maximum extent possible under the law.

1.3 Trademark
"TokReducer" is a trademark of the Owner. Use of the TokReducer name in any product, service, marketing material, or publication without prior written authorization is prohibited. This includes competing products, academic papers, press releases, and social media.

2. License Types

TokReducer is commercial software. It is not open source. The following license tiers are available. All licenses require acceptance of the terms in Section 4.

Tier            | Scope                                    | Source Access    | Pricing
Evaluation      | 1 developer, non-production, 14 days     | None             | Free -- by application
Developer       | 1 developer, up to 3 production apps     | Python only      | Contact for pricing
Team            | Up to 10 developers, unlimited apps      | Python + Rust    | Contact for pricing
Enterprise      | Unlimited developers, on-premises rights | Full source      | Contact for pricing
OEM             | Embed in third-party products            | Full source+docs | Separate agreement

2.1 Evaluation license
- Duration: 14 days from activation date
- Single developer, non-production environments only
- No commercial deployment, no API resale, no redistribution
- Token limit: 500,000 tokens compressed per day
- Requires signed evaluation agreement and Owner approval
- Must upgrade to a paid license before any production use

2.2 Developer license
- Single developer, up to three production applications
- Commercial use permitted
- No resale or white-labeling of TokReducer itself
- Python library source access only

2.3 Team license
- Up to ten developers, unlimited internal applications
- Full commercial use, including REST API proxy deployment
- Python and Rust library source access
- Up to 50 custom compression rule entries
- Priority support channel included

2.4 Enterprise license
- Unlimited developers and applications
- Full source code access -- Python, Rust, and test suites
- On-premises deployment rights
- White-label rights available under separate written agreement
- Unlimited custom compression rules
- Dedicated support with 4-hour SLA

2.5 OEM / Integration license
For companies embedding TokReducer into products for redistribution. Requires a separate written agreement. Contact the Owner directly.

Pricing policy
TokReducer does not publish fixed pricing. All license pricing is determined through a personal demo and consultation with the Owner. This ensures pricing is appropriate for your specific use case, team size, and token volume.

3. Restrictions

Regardless of license tier, the following are strictly prohibited without separate written authorization:

1. Reverse engineering, decompiling, or disassembling any part of TokReducer software
2. Creating derivative compression protocols based on TokReducer's methodology and marketing them as original
3. Sublicensing, selling, or transferring your license to a third party
4. Using TokReducer to build a product that directly competes with TokReducer
5. Removing or altering any copyright, trademark, or proprietary notices
6. Claiming ownership or co-authorship of the TokReducer protocol or software
7. Publishing benchmark comparisons or performance data without written consent
8. Using TokReducer trademarks in domain names, product names, or company names
9. Training machine learning models on TokReducer source code or documentation
10. Deploying TokReducer in military weapons systems, mass surveillance, or illegal activities

4. General Terms

4.1 License grant
Subject to payment of applicable fees and compliance with this Agreement, the Owner grants Licensee a non-exclusive, non-transferable, revocable license to use TokReducer solely as specified in the applicable license tier. This Agreement transfers no ownership interest in TokReducer.

4.2 Updates
Active license holders receive updates within their major version (e.g., 1.x). Upgrades to future major versions may require license renewal at the Owner's discretion. Security patches are provided free of charge to all active license holders.

4.3 Termination
The Owner may terminate any license immediately and without refund upon breach of any term of this Agreement. Upon termination, all copies of TokReducer software must be deleted and the Licensee must certify destruction in writing within seven days.

4.4 Warranty disclaimer
TOKREDUCER IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. THE OWNER MAKES NO WARRANTIES REGARDING ACCURACY, RELIABILITY, OR COMPLETENESS. USE OF TOKREDUCER IS AT LICENSEE'S SOLE RISK.

4.5 Limitation of liability
IN NO EVENT SHALL THE OWNER BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES ARISING FROM USE OR INABILITY TO USE TOKREDUCER, INCLUDING LOSS OF DATA, REVENUE, OR BUSINESS OPPORTUNITIES.

4.6 Governing law
This Agreement is governed by applicable international intellectual property law and the laws of the jurisdiction of the Owner's residence. Disputes shall be resolved through binding arbitration before resorting to litigation.

4.7 Entire agreement
This Agreement constitutes the entire agreement between the parties regarding TokReducer and supersedes all prior negotiations, representations, and understandings. No modification is binding unless made in writing and signed by the Owner.

5. Trade Secret Protection

The following components are designated as trade secrets protected under applicable law. Licensees with access to these components must maintain strict confidentiality and must sign a separate Non-Disclosure Agreement prior to receiving access.

- The compression heuristic engine and rule selection algorithms
- Compression level calibration data derived from LLM behavioral testing
- Provider-specific optimization tables for OpenAI, Anthropic, Google, and others
- The length mirroring detection and correction methodology
- Internal benchmark data comparing TokReducer against competing approaches
- System prompt injection templates for each compression level
- Customer usage data, token reduction statistics, and performance metrics

Breach of trade secret obligations may result in injunctive relief and monetary damages in addition to termination of the license.

6. How to Obtain a License

All licenses are issued personally. There is no automated purchase flow. Every license is discussed directly with the Owner.

Step 1 -- Visit the TokReducer website and submit a demo request.
Step 2 -- Describe your use case, team size, and expected token volume.
Step 3 -- The Owner will contact you within 48 hours to schedule a demo.
Step 4 -- Attend the personal demo call.
Step 5 -- Discuss requirements and agree on pricing.
Step 6 -- Sign the license agreement and receive your license key.

7. Acknowledgement & Signature

By using TokReducer in any capacity, you acknowledge that you have read, understood, and agree to be bound by the terms of this Agreement.

TokReducer -- Proprietary Software -- All Rights Reserved
For licensing inquiries, visit the TokReducer website or contact the Owner directly.`;

export default function Agreement() {
  const { user } = useAuth();
  const [status, setStatus] = useState<{ accepted: boolean } | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      checkAgreement()
        .then(setStatus)
        .catch(() => {});
    }
  }, [user]);

  async function handleAccept() {
    setAccepting(true);
    setError(null);
    try {
      await acceptAgreement();
      setStatus({ accepted: true });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setAccepting(false);
    }
  }

  return (
    <section className="page agreement-page">
      <h2>TokReducer License Agreement</h2>
      <div className="agreement-text">
        <pre>{LICENSE_TEXT}</pre>
      </div>

      {user && status && !status.accepted && (
        <div className="agreement-action">
          <p>You must accept this agreement to use TokReducer.</p>
          <button
            className="btn primary"
            onClick={handleAccept}
            disabled={accepting}
          >
            {accepting ? "Accepting..." : "I Accept This Agreement"}
          </button>
          {error && <div className="msg err">{error}</div>}
        </div>
      )}

      {user && status?.accepted && (
        <div className="msg ok" style={{ marginTop: 16 }}>
          You have accepted this agreement.
        </div>
      )}
    </section>
  );
}
