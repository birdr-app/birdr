import { Box, Heading } from "@chakra-ui/react";
import { useContext, useEffect, useRef } from "react";
import AppContext from "../core/app-context";
import { FormattedMessage, useIntl } from "react-intl";
import { type TaxOrder, UseTaxOrder } from "../user/use-tax-order";
import TaxOrderCombobox from "./tax-order-combobox";

const SelectTaxOrder = () => {
  const intl = useIntl();
  const { taxOrders } = UseTaxOrder();
  const { taxOrder, setTaxOrder, setSpeciesGroup, game } = useContext(AppContext);
  const syncedGameToken = useRef<string | null>(null);

  useEffect(() => {
    if (!game?.token) {
      syncedGameToken.current = null;
      return;
    }
    if (!game.tax_order || syncedGameToken.current === game.token) return;
    const orders = Array.isArray(taxOrders) ? taxOrders : [];
    const foundTaxOrder = orders.find((t) => t.tax_order === game.tax_order);
    if (foundTaxOrder && setTaxOrder) {
      setTaxOrder(foundTaxOrder);
      syncedGameToken.current = game.token;
    }
  }, [game?.token, game?.tax_order, taxOrders, setTaxOrder]);

  const onChange = (orderName: string | undefined) => {
    if (!orderName) {
      setTaxOrder?.(undefined);
      return;
    }
    const orders = Array.isArray(taxOrders) ? taxOrders : [];
    const found = orders.find((t) => t.tax_order === orderName);
    setTaxOrder?.(found);
    if (found) setSpeciesGroup?.(undefined);
  };

  const placeholder = intl.formatMessage({
    id: "select order placeholder",
    defaultMessage: "Select order...",
  });

  return (
    <Box>
      <Heading size={"md"} mb={4}>
        <FormattedMessage id={"tax order"} defaultMessage={"Taxonomic order"} />
      </Heading>
      <TaxOrderCombobox
        taxOrders={Array.isArray(taxOrders) ? taxOrders : []}
        value={taxOrder?.tax_order}
        onChange={onChange}
        placeholder={placeholder}
        allowAll={false}
      />
    </Box>
  );
};

export default SelectTaxOrder;
