import type { Row } from "../lib/resource"
import BillingRulesEditor from "./BillingRulesEditor"
import CreditTermsEditor from "./CreditTermsEditor"

/** The corporate account editor's extra panels: credit terms, then billing rules. */
export default function CompanyExtras(props: { row: Row; reload: () => void }) {
  return (
    <div className="space-y-4">
      <CreditTermsEditor {...props} />
      <BillingRulesEditor {...props} />
    </div>
  )
}
