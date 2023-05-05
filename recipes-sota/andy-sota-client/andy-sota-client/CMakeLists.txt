cmake_minimum_required (VERSION 3.5)

add_executable(andy-sota-client main.cc)
target_compile_definitions(andy-sota-client PRIVATE BOOST_LOG_DYN_LINK)
#target_include_directories(andy-sota-client PRIVATE ${AKLITE_DIR}/include ${AKTUALIZR_DIR}/third_party/jsoncpp/include ${AKTUALIZR_DIR}/src/libaktualizr/logging)
target_link_libraries(andy-sota-client boost_log pthread aktualizr_lite aktualizr)
install(TARGETS andy-sota-client RUNTIME DESTINATION bin)
