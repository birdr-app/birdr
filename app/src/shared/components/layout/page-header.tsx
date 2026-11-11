import {ReactElement, ReactNode} from "react";
import {Flex, Button, HStack, Avatar, Text} from "@chakra-ui/react";
import {GiHamburgerMenu} from "react-icons/gi";
import {FaUserCircle, FaArrowLeft} from "react-icons/fa";
import {useMenu} from "./menu-context";
import {useAuthProfile} from "../../../core/auth-profile-context";
import {getAvatarUrl} from "../../../api/services/profile.service";

const PageHeader = ({children, onBack, backLabel, backFlag}: {children: ReactElement | ReactNode[], onBack?: () => void, backLabel?: string, backFlag?: string} ) => {
  const {onOpenMenu, onOpenUserMenu} = useMenu();
  const {isAuthenticated, profile, userEmail} = useAuthProfile();

  return (
    <Flex
      direction={'row'}
      justifyContent='space-between'
      alignItems={'center'}
      pl={2} pr={2} py={2}
      backgroundColor={'secondary.200'}
      position={'fixed'}
      width={'full'}
      zIndex={10}
      shadow={'md'}
      gap={2}
    >
      {/* Left menu button */}
      <Button variant="ghost" color={'gray.800'} p={2} onClick={onOpenMenu} size="sm">
        <GiHamburgerMenu size={20}/>
      </Button>
      {onBack ? (
        <Button variant="ghost" color={'gray.800'} p={2} onClick={onBack} size="sm" aria-label={backLabel || 'Back'} data-testid="trip-back-link">
          <FaArrowLeft size={18}/>
          {backFlag ? <span style={{fontSize: 18, lineHeight: 1}}>{backFlag}</span> : null}
        </Button>
      ) : null}
      
      {/* Center content (title) */}
      <Flex flex={1} justifyContent="center" alignItems="center">
        {children}
      </Flex>
      
      {/* Right user menu button */}
      <Button 
        variant="ghost" 
        color={'gray.800'} 
        p={2} 
        onClick={onOpenUserMenu} 
        size="sm"
      >
        {isAuthenticated ? (
          <HStack gap={2}>
            <Avatar.Root size="sm">
              {getAvatarUrl(profile) ? (
                <Avatar.Image src={getAvatarUrl(profile)!} alt={profile?.username || userEmail || "User"} />
              ) : null}
              <Avatar.Fallback>
                {(profile?.username || userEmail || "User").charAt(0).toUpperCase()}
              </Avatar.Fallback>
            </Avatar.Root>
            <Text fontSize="sm" fontWeight="medium" display={{ base: 'none', md: 'block' }}>
              {profile?.username || userEmail || "User"}
            </Text>
          </HStack>
        ) : (
          <FaUserCircle size={20}/>
        )}
      </Button>
    </Flex>
  )
};

export default PageHeader;
