import { useState } from "react"
import { Upload, CookingPot } from "lucide-react"
import { ResourceScreen } from "../components/ResourceScreen"
import { Button } from "../components/ui/button"
import { useAuth } from "../lib/auth"
import { menuItemsConfig } from "./configs"
import MenuImport from "./MenuImport"
import RecipeManager from "./RecipeManager"
import { t as translate, useUILanguage } from "../lib/i18n"

/** The Menu screen: the generic resource list plus bulk upload. Menu Item is
 * writable by Finance / F&B Manager / Hotel Admin / System Manager (Front Desk is read-only
 * on the doctype), so the import button follows the same line. */

const MENU_WRITE_ROLES = [
  "Finance",
  "F&B Manager",
  "Hotel Admin",
  "System Manager",
  "Administrator",
]

export default function MenuItems() {
  useUILanguage()
  const { roles } = useAuth()
  const canImport = roles.some((r) => MENU_WRITE_ROLES.includes(r))
  const [importing, setImporting] = useState(false)
  const [recipes, setRecipes] = useState(false)
  // bumping the key remounts the list so imported rows show up
  const [reloadKey, setReloadKey] = useState(0)

  return (
    <>
      <ResourceScreen
        key={reloadKey}
        config={menuItemsConfig}
        headerAction={
          canImport ? (
            <>
              {/* Recipes live behind the Menu, not the Inventory screen: you
                  edit what a dish is made of while you are thinking about the
                  dish. ResourceScreen is flat-field CRUD with no child-table
                  support, so this opens its own editor. */}
              <Button variant="outline" onClick={() => setRecipes(true)}>
                <CookingPot className="mr-1 size-4" aria-hidden />{translate("Recipes")}</Button>
              <Button variant="outline" onClick={() => setImporting(true)}>
                <Upload className="mr-1 size-4" aria-hidden />{translate("Bulk upload")}</Button>
            </>
          ) : undefined
        }
      />
      {importing && (
        <MenuImport
          onClose={() => setImporting(false)}
          onDone={() => setReloadKey((k) => k + 1)}
        />
      )}
      {recipes && <RecipeManager onClose={() => setRecipes(false)} />}
    </>
  )
}
