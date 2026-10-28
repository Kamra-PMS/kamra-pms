import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Plus } from "lucide-react"

import { ResourceScreen } from "../components/ResourceScreen"
import GroupBookingDialog from "../components/GroupBookingDialog"
import { Button } from "../components/ui/button"
import { useT } from "../lib/i18n"
import { groupsConfig } from "./configs"

/** Groups & Blocks with a "New group booking" flow (?new=1 opens it). */
export default function Groups() {
  const { t } = useT()
  const [params, setParams] = useSearchParams()
  const [creating, setCreating] = useState(false)
  useEffect(() => {
    if (params.get("new") === "1") setCreating(true)
  }, [params])
  // bumping the key remounts the list so the new group shows up
  const [reloadKey, setReloadKey] = useState(0)
  const close = () => {
    setCreating(false)
    if (params.has("new")) setParams({}, { replace: true })
  }

  return (
    <>
      <ResourceScreen
        key={reloadKey}
        config={groupsConfig}
        headerAction={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" aria-hidden />
            {t("New group booking")}
          </Button>
        }
      />
      {creating && (
        <GroupBookingDialog
          onClose={close}
          onDone={() => {
            close()
            setReloadKey((k) => k + 1)
          }}
        />
      )}
    </>
  )
}
