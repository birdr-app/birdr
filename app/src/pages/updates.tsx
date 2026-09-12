import { Heading, VStack } from "@chakra-ui/react";
import { Page } from "../shared/components/layout";
import {FormattedMessage} from "react-intl";
import {useContext, useEffect, useState} from "react"
import AppContext from "../core/app-context"
import {Loading} from "../components/loading"
import {UpdateListItemCard} from "../components/updates/update-list-item"
import {loadUpdates, type UpdateListItem} from "../core/updates"

const UpdatesPage = () => {
  const {loading, setLoading, player, appLanguage} = useContext(AppContext)
  const [updates, setUpdates] = useState<UpdateListItem[]>([])

  useEffect(() => {
    setLoading(true)
    loadUpdates(player?.token, appLanguage || 'en')
      .then((items) => {
        setUpdates(items)
        setLoading(false)
      })
  }, [player?.token, appLanguage, setLoading]);

  return (
    <Page>
      <Page.Header>
        <Heading color={'gray.800'} size={'lg'} m={0}>
          <FormattedMessage id='updates' defaultMessage={'Updates'}/>
        </Heading>
      </Page.Header>
      <Page.Body>
        <>
          {loading ? (
            <Loading/>
          ) : (
            <VStack align="stretch" gap={4}>
              {updates.map((update) => (
                <UpdateListItemCard key={update.id} update={update} />
              ))}
            </VStack>
          )}
        </>
      </Page.Body>
    </Page>

  )
};

export default UpdatesPage;