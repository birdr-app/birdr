import {Outlet} from "react-router-dom";
import {
  Box,
  DrawerRoot,
  DrawerBody,
  DrawerCloseTrigger,
  DrawerContent,
  DrawerFooter,
  DrawerBackdrop,
  Flex,
  Link,
  useDisclosure,
} from "@chakra-ui/react";
import {useState} from "react";
import {BirdrMenu} from "./menu";
import {UserMenu} from "./user-menu";
import {LoginModal} from "../../../components/auth/login-modal";
import {MenuProvider} from "./menu-context";
import {OpenInAppOnLoad} from "../../../components/open-in-app-on-load";

const Layout = () => {
  const {open: isOpen, onOpen, onClose} = useDisclosure()
  const {open: isUserMenuOpen, onOpen: onUserMenuOpen, onClose: onUserMenuClose} = useDisclosure()
  const {open: isLoginModalOpen, onOpen: onLoginModalOpen, onClose: onLoginModalClose} = useDisclosure()
  const [loginModalMode, setLoginModalMode] = useState<'login' | 'register'>('login');

  const handleUserIconClick = () => {
    onUserMenuOpen();
  };

  return (
    <MenuProvider onOpenMenu={onOpen} onOpenUserMenu={handleUserIconClick}>
      <OpenInAppOnLoad />
      <Outlet/>
      
      {/* Left drawer - Main menu */}
      <DrawerRoot
        open={isOpen}
        placement='start'
        onOpenChange={(e: { open: boolean }) => !e.open && onClose()}
      >
        <DrawerBackdrop/>
        <DrawerContent height="100vh" maxHeight="100vh" display="flex" flexDirection="column" position="fixed" top={0} left={0} right="auto" bottom={0} bg="white">
          <DrawerCloseTrigger/>
          <DrawerBody flex="1" overflowY="auto" mt={4} minHeight={0} bg="white">
            <BirdrMenu/>
          </DrawerBody>

          <DrawerFooter bg="white">
            <Flex direction={'column'} gap={4}>
              <Box>
                Developed by <b>GoedLoek</b>
              </Box>
              <Box>
                Contact <Link color='primary.500' href={'mailto:info@goedloek.nl'}>info@goedloek.nl</Link>
              </Box>
            </Flex>
          </DrawerFooter>
        </DrawerContent>
      </DrawerRoot>

      {/* Right drawer - User menu */}
      <DrawerRoot
        open={isUserMenuOpen}
        placement='end'
        onOpenChange={(e: { open: boolean }) => !e.open && onUserMenuClose()}
      >
        <DrawerBackdrop/>
        <DrawerContent height="100vh" maxHeight="100vh" display="flex" flexDirection="column" position="fixed" top={0} right={0} left="auto" bottom={0} bg="white">
          <DrawerCloseTrigger/>
          <DrawerBody flex="1" overflowY="auto" minHeight={0} bg="white" p={6}>
            <UserMenu
              isOpen={isUserMenuOpen}
              onOpenLoginModal={(mode) => {
                setLoginModalMode(mode);
                onLoginModalOpen();
                onUserMenuClose();
              }}
            />
          </DrawerBody>
        </DrawerContent>
      </DrawerRoot>

      {/* Login Modal */}
      <LoginModal 
        isOpen={isLoginModalOpen} 
        onClose={onLoginModalClose}
        defaultMode={loginModalMode}
      />
    </MenuProvider>
  )
};

export default Layout;
